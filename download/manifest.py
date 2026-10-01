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
from base64 import b64decode
from dataclasses import dataclass, field
from typing import Any, Dict, List, Literal
from xml.etree import ElementTree

DASH_NS = "{urn:mpeg:dash:schema:mpd:2011}"

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


def _dash_find(parent: ElementTree.Element, tag: str) -> ElementTree.Element | None:
    """Find a direct child by local name, ignoring namespace.

    ``ElementTree.find`` only honours a ``{ns}`` prefix on the first step of a
    path, so a nested path like ``Period/AdaptationSet/Representation`` cannot be
    namespace-qualified throughout. Walking children by local name avoids that
    limitation entirely.
    """
    for child in parent:
        if not isinstance(child.tag, str):
            continue  # comments and processing instructions
        local = child.tag.rsplit("}", 1)[-1]
        if local == tag:
            return child
    return None


def _parse_dash_xml(decoded: str) -> tuple[List[str], str, str]:
    """Parse a DASH MPD into segment URLs.

    Only the first ``AdaptationSet``/``Representation`` is considered, which
    matches the single-audio-representation manifests Tidal emits for tracks.
    """
    try:
        tree = ElementTree.fromstring(decoded)
    except ElementTree.ParseError as exc:
        raise ManifestError(f"DASH manifest is not valid XML: {exc}") from exc

    period = _dash_find(tree, "Period")
    if period is None:
        raise ManifestError("DASH manifest has no Period element")

    adaptation_set = _dash_find(period, "AdaptationSet")
    if adaptation_set is None:
        raise ManifestError("DASH manifest has no AdaptationSet element")

    representation = _dash_find(adaptation_set, "Representation")
    if representation is None:
        raise ManifestError("DASH manifest has no Representation element")

    codecs = representation.get("codecs") or ""
    if not codecs:
        raise ManifestError("DASH manifest Representation has no codecs")

    segment_template = _dash_find(representation, "SegmentTemplate")
    if segment_template is None:
        raise ManifestError("DASH manifest has no SegmentTemplate element")

    url_template = segment_template.get("media")
    if not url_template:
        raise ManifestError("DASH SegmentTemplate has no media attribute")

    timeline = _dash_find(segment_template, "SegmentTimeline")
    if timeline is None:
        raise ManifestError("DASH SegmentTemplate has no SegmentTimeline")

    segments = timeline.findall(f"{DASH_NS}S")
    if not segments:
        raise ManifestError("DASH SegmentTimeline contains no segments")

    # Each <S> element contributes one segment, plus `r` repeats. A negative `r`
    # signals a time-based (rather than count-based) timeline, which Tidal does
    # not use for track manifests, so it is rejected instead of mis-expanded.
    total = 0
    for segment in segments:
        total += 1
        repeats = segment.get("r")
        if repeats is None:
            continue
        try:
            repeat_count = int(repeats)
        except ValueError as exc:
            raise ManifestError(
                f"DASH segment has non-numeric r={repeats!r}") from exc
        if repeat_count < 0:
            raise ManifestError(
                "DASH SegmentTimeline uses negative repeat counts, which are "
                "time-based and not supported"
            )
        total += repeat_count

    if "$Number$" not in url_template:
        if total != 1:
            raise ManifestError(
                "DASH media template has no $Number$ placeholder but the "
                "timeline describes multiple segments"
            )
        return [url_template], codecs, "NONE"

    urls = [url_template.replace("$Number$", str(index))
            for index in range(total)]
    return urls, codecs, "NONE"


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
