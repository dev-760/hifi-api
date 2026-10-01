"""Tidal interaction for downloads: resolve streams, then fetch audio bytes.

The flow deliberately splits into two phases with different concurrency rules.

Phase 1 - resolving a manifest - needs a *playback* credential, because Tidal
tiers playback access per account. This phase is short.

Phase 2 - downloading segments - hits the CDN using the unauthenticated URLs
that came out of the manifest. No credential is involved, so holding an account
lease for the duration of a multi-hundred-megabyte transfer would needlessly
serialise downloads behind the (typically single) playback account.

That is why :func:`fetch_track_stream` and :func:`download_segments` are
separate and why the caller releases the lease between them.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import AsyncIterator, Optional

import httpx

from .manifest import ManifestError, ParsedManifest, parse_manifest

logger = logging.getLogger(__name__)

# Convenience aliases for Tidal's quality names. These are additive only: where
# an alias would shadow a real Tidal quality it is deliberately absent, because
# the rest of this API (notably /track/) already speaks Tidal's vocabulary.
#
#   LOW / HIGH / LOSSLESS / HI_RES_LOSSLESS   native, preferred
#   low / normal / max                        alias
#
# Note tiddl's "high" alias means LOSSLESS, but Tidal has a genuine HIGH tier
# (320 kbps AAC). Prefer "lossless" for the lossless tier rather than silently
# returning something other than what the caller asked for.
QUALITY_ALIASES = {
    "low": "LOW",
    "normal": "HIGH",
    "lossless": "LOSSLESS",
    "max": "HI_RES_LOSSLESS",
    # Tidal spells it HI_RES_LOSSLESS; people reasonably type HIRES_LOSSLESS.
    "hires_lossless": "HI_RES_LOSSLESS",
    "hires": "HI_RES_LOSSLESS",
}

VALID_QUALITIES = frozenset({"LOW", "HIGH", "LOSSLESS", "HI_RES_LOSSLESS"})

PLAYBACK_INFO_URL = "https://api.tidal.com/v1/tracks/{track_id}/playbackinfopaywall"

CHUNK_SIZE = 1024 * 1024


def _canonical(value: str) -> str:
    """Fold case and separator style so HI_RES/HI-RES/hires are one quality."""
    return re.sub(r"[\s_\-]+", "_", value.strip()).upper()


def normalize_quality(quality: str) -> str:
    """Map a user-supplied quality onto Tidal's own naming.

    Tidal's native names are matched first and case-insensitively, then the
    additive aliases above. Raises ``ValueError`` for anything unrecognised so
    that a typo surfaces as a 422 rather than an opaque upstream 400.
    """
    candidate = (quality or "").strip()
    canonical = _canonical(candidate)
    if canonical in VALID_QUALITIES:
        return canonical
    mapped = QUALITY_ALIASES.get(candidate.lower())
    if mapped:
        return mapped
    raise ValueError(
        f"Unsupported quality {quality!r}; expected one of "
        f"{sorted(VALID_QUALITIES)} or aliases {sorted(QUALITY_ALIASES)}"
    )


async def fetch_track_stream(
    client: httpx.AsyncClient,
    token: str,
    track_id: int,
    quality: str,
    *,
    country_code: str,
    immersive_audio: bool = False,
) -> ParsedManifest:
    """Resolve a track's playback manifest.

    Must be called while holding a playback credential lease, since the caller
    supplies the bearer token.
    """
    params = {
        "audioquality": quality,
        "playbackmode": "STREAM",
        "assetpresentation": "FULL",
        "countryCode": country_code,
    }
    if immersive_audio:
        params["immersiveaudio"] = "true"

    response = await client.get(
        PLAYBACK_INFO_URL.format(track_id=track_id),
        params=params,
        headers={"authorization": f"Bearer {token}"},
    )
    response.raise_for_status()
    payload = response.json()

    manifest_b64 = payload.get("manifest")
    if not manifest_b64:
        raise ManifestError(f"Tidal returned no manifest for track {track_id}")

    return parse_manifest(
        manifest_b64,
        payload.get("manifestMimeType", ""),
        audio_mode=payload.get("audioMode", "STEREO"),
        audio_quality=payload.get("audioQuality", quality),
        bit_depth=payload.get("bitDepth"),
        sample_rate=payload.get("sampleRate"),
    )


async def iter_segment(client: httpx.AsyncClient, url: str) -> AsyncIterator[bytes]:
    """Yield the bytes of a single CDN segment."""
    async with client.stream("GET", url) as response:
        response.raise_for_status()
        async for chunk in response.aiter_bytes(CHUNK_SIZE):
            yield chunk


async def download_segments(
    client: httpx.AsyncClient,
    urls: list[str],
    *,
    on_progress=None,
    retry_delays: tuple[float, ...] = (1.0, 3.0),
) -> AsyncIterator[bytes]:
    """Yield the concatenated payload of every segment in order.

    Segments are plain CDN resources, so a failure here is usually transient.
    Retries are per-segment: a partially written download is discarded by the
    caller's atomic write, so restarting one segment is always safe.
    """

    async def fetch_with_retry(url: str) -> bytes:
        last_error: Optional[Exception] = None
        for attempt in range(len(retry_delays) + 1):
            try:
                chunks = [chunk async for chunk in iter_segment(client, url)]
                return b"".join(chunks)
            except (httpx.HTTPError, httpx.StreamError) as exc:
                last_error = exc
                if attempt >= len(retry_delays):
                    break
                delay = retry_delays[attempt]
                logger.warning(
                    "Segment fetch failed (%s), retrying in %.1fs", exc, delay
                )
                await asyncio.sleep(delay)
        raise RuntimeError(
            f"Failed to fetch segment after retries: {last_error}")

    downloaded = 0
    for url in urls:
        data = await fetch_with_retry(url)
        downloaded += len(data)
        if on_progress is not None:
            on_progress(downloaded)
        yield data
