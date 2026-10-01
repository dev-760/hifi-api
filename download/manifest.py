"""Parse Tidal playback manifests into CDN segment URLs.

Ported from the approach used by `tiddl <https://github.com/oskvr37/tiddl>`_.

A Tidal playback manifest is a base64 blob whose interpretation depends on
``manifestMimeType``:

``application/vnd.tidal.bts``
    A small JSON document with an explicit ``urls`` array. Covers LOW, HIGH and
    LOSSLESS qualities.

``application/dash+xml``
    A MPEG-DASH MPD document. HI_RES_LOSSLESS and Dolby Atmos arrive this way.
    Segment URLs are described by a ``SegmentTemplate`` whose ``media``
    attribute contains a ``$Number$`` placeholder expanded against the
    ``SegmentTimeline``.

Both paths are parsed here into a flat list of URLs. No decryption is
performed: the v1 ``playbackinfopaywall`` manifests are served unencrypted, and
``encryptionType`` is validated rather than acted upon so that an unexpected
change upstream fails loudly instead of writing garbage to disk.
"""

from __future__ import annotations

import json
import re
from base64 import b64decode
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal

MANIFEST_MIME_BTS = "application/vnd.tidal.bts"
MANIFEST_MIME_DASH = "application/dash+xml"

# Codecs that arrive in an MP4 container rather than a raw FLAC stream.
DOLBY_CODECS = frozenset({"eac3", "ac4"})

# Only unencrypted manifests are supported. Tidal does not serve anything else
# on the v1 playbackinfopaywall endpoint today, so anything encrypted means the
# upstream contract changed and we should stop rather than emit unplayable data.
SUPPORTED_ENCRYPTION = frozenset({"NONE", ""})


class ManifestError(ValueError):
    """Raised when a manifest cannot be parsed or uses an unsupported feature."""


@dataclass(frozen=True)
class ParsedManifest:
    """Flattened view of a playback manifest."""

    urls: List[str]
    codecs: str
    mime_type: str
    encryption_type: str
    audio_mode: str = "STEREO"
    audio_quality: str = ""
    bit_depth: int | None = None
    sample_rate: int | None = None

    @property
    def file_extension(self) -> str:
        """Container extension implied by the codec and requested quality.

        HI_RES_LOSSLESS is served as FLAC-in-MP4, so the correct extension is
        ``.m4a`` even though the codec string says ``flac``.
        """
        if self.codecs == "flac":
            if self.audio_quality == "HI_RES_LOSSLESS":
                return ".m4a"
            return ".flac"
        if self.codecs.startswith("mp4") or self.codecs in DOLBY_CODECS:
            return ".m4a"
        raise ManifestError(f"Unsupported codec {self.codecs!r}")

    @property
    def needs_flac_extraction(self) -> bool:
        """True when the payload is FLAC wrapped in MP4 and must be remuxed."""
        return (
            self.codecs == "flac"
            and self.audio_quality == "HI_RES_LOSSLESS"
        )

    def describe(self) -> Dict[str, Any]:
        """JSON-safe summary for API responses."""
        return {
            "urlCount": len(self.urls),
            "codecs": self.codecs,
            "mimeType": self.mime_type,
            "encryptionType": self.encryption_type or "NONE",
            "audioMode": self.audio_mode,
            "audioQuality": self.audio_quality,
            "bitDepth": self.bit_depth,
            "sampleRate": self.sample_rate,
            "fileExtension": self.file_extension,
            "needsFlacExtraction": self.needs_flac_extraction,
        }


def decode_manifest(manifest: str) -> str:
    """Base64-decode a manifest blob into text."""
    if not manifest:
        raise ManifestError("Manifest is empty")
    try:
        return b64decode(manifest, validate=True).decode("utf-8")
    except Exception as exc:  # noqa: BLE001 - surfaced as a manifest failure
        raise ManifestError(
            f"Manifest is not valid base64 UTF-8: {exc}") from exc


def _parse_bts(decoded: str) -> tuple[List[str], str, str]:
    """Parse the JSON-based BTS manifest."""
    try:
        payload = json.loads(decoded)
    except json.JSONDecodeError as exc:
        raise ManifestError(f"BTS manifest is not valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise ManifestError("BTS manifest must be a JSON object")

    urls = payload.get("urls")
    if not isinstance(urls, list) or not urls:
        raise ManifestError("BTS manifest has no usable urls")

    cleaned = [u for u in urls if isinstance(u, str) and u]
    if not cleaned:
        raise ManifestError("BTS manifest urls are all empty or malformed")

    codecs = payload.get("codecs") or ""
    if not isinstance(codecs, str):
        raise ManifestError("BTS manifest codecs must be a string")

    encryption = payload.get("encryptionType") or "NONE"
    if not isinstance(encryption, str):
        raise ManifestError("BTS manifest encryptionType must be a string")

    return cleaned, codecs, encryption


def _parse_dash_xml(decoded: str) -> tuple[List[str], str, str]:
    """Extract segment URLs from a Tidal DASH MPD.

    Tidal's real manifests are **not valid XML**. A live ``LOSSLESS`` manifest
    captured from the API has four independent defects:

    1. ``segmentAlignment="true"`` is repeated on the same start tag.
    2. ``<Representation>`` sits directly under ``<MPD>``, with no
       ``<Period>`` or ``<AdaptationSet>`` wrapper.
    3. The ``initialization`` attribute is **never terminated** - its value, a
       base64 ``Policy``/``Signature`` blob, runs directly into ``</AdaptationSet>``.
    4. The document ends with ``</MAP>`` instead of ``</MPD>``.

    A conforming parser cannot read this, so rather than repairing malformed
    XML with increasingly elaborate heuristics, the handful of attributes
    actually needed are pulled out with targeted patterns. Two payload layouts
    occur upstream:

    * **Segmented** - a ``media`` template plus ``SegmentTimeline``, with
      ``$Number$`` expanded across the segments.
    * **Single file** - only an ``initialization`` URL and no timeline, meaning
      the whole track is one URL.
    """
    codecs_match = re.search(r'codecs="([^"]*)"', decoded)
    codecs = codecs_match.group(1) if codecs_match else ""

    media_match = _extract_attribute(decoded, "media")
    timeline_match = re.search(r"<SegmentTimeline\b", decoded)
    init_match = _extract_attribute(decoded, "initialization")

    start_number = _extract_attribute(decoded, "startNumber")

    # Segmented layout: a media template expanded across the timeline.
    if media_match and timeline_match:
        total = _count_timeline_segments(decoded)
        start = int(
            start_number) if start_number and start_number.isdigit() else 1

        if "$Number$" not in media_match:
            if total != 1:
                raise ManifestError(
                    "DASH media template has no $Number$ placeholder but the "
                    "timeline describes multiple segments"
                )
            return [media_match], codecs, "NONE"

        return (
            [
                media_match.replace("$Number$", str(index))
                for index in range(start, start + total)
            ],
            codecs,
            "NONE",
        )

    # Single-file layout: one initialization URL, no timeline.
    if init_match:
        return [init_match], codecs, "NONE"

    if media_match:
        return [media_match], codecs, "NONE"

    base_url = _extract_base_url(decoded)
    if base_url:
        return [base_url], codecs, "NONE"

    raise ManifestError(
        "DASH manifest contains neither a media template with a SegmentTimeline "
        "nor an initialization URL"
    )


def _extract_attribute(xml_text: str, name: str) -> str | None:
    """Pull one attribute value out of a possibly malformed document.

    Handles both a properly quoted value and the live case where the value is
    unterminated and runs until the stray closing markup begins.
    """
    quoted = re.search(rf'\b{name}="([^"]*)"', xml_text)
    if quoted:
        return _unescape_xml(quoted.group(1))

    # Unterminated: the value runs on until a '<' that starts stray markup.
    # Everything between the opening quote and that '<' is the value.
    unterminated = re.search(rf'\b{name}="([^<]*)', xml_text)
    if unterminated:
        value = unterminated.group(1).rstrip()
        return _unescape_xml(value) if value else None

    return None


def _extract_base_url(xml_text: str) -> str | None:
    """Read a ``<BaseURL>`` element, which some manifests use instead of ``media``."""
    match = re.search(r"<BaseURL[^>]*>([^<]+)</BaseURL>", xml_text, re.DOTALL)
    if match:
        value = match.group(1).strip()
        return _unescape_xml(value) if value else None
    return None


def _count_timeline_segments(xml_text: str) -> int:
    """Count segments described by a ``SegmentTimeline``.

    Each ``<S>`` contributes one segment plus its ``r`` repeat count. A negative
    ``r`` denotes a time-based timeline, which is rejected rather than
    silently mis-expanded.
    """
    timeline = re.search(
        r"<SegmentTimeline\b[^>]*>(.*?)</SegmentTimeline>", xml_text, re.DOTALL)
    if not timeline:
        return 0

    body = timeline.group(1)
    total = 0
    for match in re.finditer(r"<S\b([^>]*?)/?>", body):
        total += 1
        repeat = re.search(r'\br="(-?\d+)"', match.group(1))
        if repeat:
            count = int(repeat.group(1))
            if count < 0:
                raise ManifestError(
                    "DASH SegmentTimeline uses negative repeat counts, which are "
                    "time-based and not supported"
                )
            total += count

    return total


def _unescape_xml(value: str) -> str:
    """Decode the XML entities that appear in Tidal's URLs."""
    if "&amp;" not in value and "&quot;" not in value and "&lt;" not in value:
        return value
    return (
        value.replace("&amp;", "&")
        .replace("&quot;", '"')
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&apos;", "'")
    )


def parse_manifest(
    manifest: str,
    mime_type: str,
    *,
    audio_mode: str = "STEREO",
    audio_quality: str = "",
    bit_depth: int | None = None,
    sample_rate: int | None = None,
) -> ParsedManifest:
    """Parse a base64 Tidal manifest into a :class:`ParsedManifest`.

    Args:
        manifest: Base64-encoded manifest from ``playbackinfopaywall``.
        mime_type: The ``manifestMimeType`` reported by Tidal.
        audio_mode: ``STEREO`` or ``DOLBY_ATMOS``.
        audio_quality: Requested quality, needed to pick the right extension.
        bit_depth: Optional bit depth reported by Tidal.
        sample_rate: Optional sample rate reported by Tidal.
    """
    decoded = decode_manifest(manifest)

    if mime_type == MANIFEST_MIME_BTS:
        urls, codecs, encryption = _parse_bts(decoded)
    elif mime_type == MANIFEST_MIME_DASH:
        urls, codecs, encryption = _parse_dash_xml(decoded)
    else:
        raise ManifestError(f"Unsupported manifest mime type {mime_type!r}")

    if encryption.upper() not in SUPPORTED_ENCRYPTION:
        raise ManifestError(
            f"Manifest is encrypted ({encryption!r}); this endpoint only "
            "supports unencrypted manifests"
        )

    parsed = ParsedManifest(
        urls=urls,
        codecs=codecs,
        mime_type=mime_type,
        encryption_type=encryption or "NONE",
        audio_mode=audio_mode,
        audio_quality=audio_quality,
        bit_depth=bit_depth,
        sample_rate=sample_rate,
    )

    # Touch the property so an unsupported codec fails here rather than at the
    # point of writing a file with a meaningless extension.
    _ = parsed.file_extension
    return parsed
