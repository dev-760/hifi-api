"""Unit tests for manifest parsing and download path handling.

These are offline tests: they exercise pure functions against synthetic
manifests plus one genuine manifest captured from the live Tidal API, so they
need no credentials and make no network calls.

Run with:
    python -m pytest tests/test_manifest.py -q
"""

from __future__ import annotations

import json
import sys
from base64 import b64encode
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from download.manifest import (  # noqa: E402
    MANIFEST_MIME_BTS,
    MANIFEST_MIME_DASH,
    ManifestError,
    parse_manifest,
)
from download.service import normalize_quality  # noqa: E402
from download.store import (  # noqa: E402
    build_track_path,
    sanitize_component,
)


def encode_bts(
    urls: list[str], codecs: str = "mp4a.40.2", encryption: str = "NONE"
) -> str:
    payload = {
        "mimeType": "audio/mp4",
        "codecs": codecs,
        "encryptionType": encryption,
        "urls": urls,
    }
    return b64encode(json.dumps(payload).encode()).decode()


def encode_dash(
    urls_template: str,
    codecs: str,
    repeats: list[int | None],
    start_number: int | None = None,
) -> str:
    segments = "".join(
        f'<S d="1000" r="{r}"/>' if r is not None else '<S d="1000"/>'
        for r in repeats
    )
    start_attr = (
        f' startNumber="{start_number}"' if start_number is not None else ""
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" type="static">'
        "<Period>"
        '<AdaptationSet mimeType="audio/mp4">'
        f'<Representation codecs="{codecs}">'
        f'<SegmentTemplate media="{urls_template}"{start_attr}>'
        f"<SegmentTimeline>{segments}</SegmentTimeline>"
        "</SegmentTemplate>"
        "</Representation>"
        "</AdaptationSet>"
        "</Period>"
        "</MPD>"
    )
    return b64encode(xml.encode()).decode()


def encode_broken_dash() -> str:
    """A manifest shaped exactly like the live Tidal ones.

    Reproduces all four defects seen in a real capture: a duplicated attribute,
    no ``Period``/``AdaptationSet`` wrapper, an unterminated ``initialization``
    attribute whose value runs into ``</AdaptationSet>``, and a root that closes
    as ``</MAP>`` instead of ``</MPD>``.
    """
    xml = (
        "<MPD xmlns=\"urn:mpeg:dash:schema:mpd:2011\" "
        "xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\" "
        "value=\"main\" segmentAlignment=\"true\" group=\"main\" "
        "segmentAlignment=\"true\">"
        '<Role schemeIDUri="urn:mpe:dash:role:2011" value="main"/>'
        '<Representation id="FLC,44100,16" codecs="flac" bangwidth="962275" '
        'audioSamplingRate="44100"/>'
        '<AudioChannelConfiguration schemeId="urn:mpeg:dash:counter:2003" '
        'value="2"/>'
        '<SegmentTemplate timescale="4410" initialization="https://sp-ad-cf.audio'
        '.tidal.com/mediatracks/AbCdEf123/0.mp4/Policy=eyJQb2xpY3kiOlt7IlJl'
        'c291cmNlIjoiaHR0cHM6Ly9zcC1hZC1jZiJ9XX0%3D&amp;Signature=XxYyZ012'
        '3QUJDREVGR0hJSktMTU5PUFFSU1RVVldYWVphYmNkZWZnaGlqa2xtbg9wcXJzdHV2d3d4eXox'
        'MjM0NTY3ODkwQUJDREVG'
        "</AddaptationSet><Period></Period></MAP>"
    )
    return b64encode(xml.encode()).decode()


def encode_dash_flat() -> str:
    """Representation directly under MPD with a BaseURL, as Tidal sometimes emits."""
    xml = (
        '<MPD xmlns="urn:mpeg:dash:schema:mpd:2011">'
        '<Representation codecs="flac" audioSamplingRate="44100">'
        "<BaseURL>https://cdn/whole.flac</BaseURL>"
        "</Representation>"
        "</MPD>"
    )
    return b64encode(xml.encode()).decode()


class TestBtsManifest:
    def test_parses_urls_and_codecs(self):
        urls = [f"https://cdn.example/seg{i}" for i in range(3)]
        manifest = parse_manifest(encode_bts(urls), MANIFEST_MIME_BTS)

        assert manifest.urls == urls
        assert manifest.codecs == "mp4a.40.2"
        assert manifest.file_extension == ".m4a"

    def test_flac_codec_yields_flac_extension(self):
        manifest = parse_manifest(
            encode_bts(["https://cdn/a"], codecs="flac"), MANIFEST_MIME_BTS
        )
        assert manifest.file_extension == ".flac"
        assert manifest.needs_flac_extraction is False

    def test_hires_flac_in_mp4_yields_m4a(self):
        manifest = parse_manifest(
            encode_bts(["https://cdn/a"], codecs="flac"),
            MANIFEST_MIME_BTS,
            audio_quality="HI_RES_LOSSLESS",
        )
        assert manifest.file_extension == ".m4a"
        assert manifest.needs_flac_extraction is True

    def test_dolby_codec_yields_m4a(self):
        manifest = parse_manifest(
            encode_bts(["https://cdn/a"], codecs="eac3"), MANIFEST_MIME_BTS
        )
        assert manifest.file_extension == ".m4a"

    def test_rejects_empty_urls(self):
        manifest = encode_bts([], codecs="mp4a.40.2")
        with pytest.raises(ManifestError, match="no usable urls"):
            parse_manifest(manifest, MANIFEST_MIME_BTS)

    def test_rejects_unknown_codec(self):
        # Validation is eager: an unusable codec fails at parse time rather than
        # at the point a file would be written with a meaningless extension.
        with pytest.raises(ManifestError, match="Unsupported codec"):
            parse_manifest(
                encode_bts(["https://cdn/a"], codecs="opus"), MANIFEST_MIME_BTS
            )


class TestEncryption:
    def test_rejects_encrypted_manifest(self):
        manifest = encode_bts(["https://cdn/a"], encryption="WIDEVINE")
        with pytest.raises(ManifestError, match="encrypted"):
            parse_manifest(manifest, MANIFEST_MIME_BTS)

    def test_accepts_none_encryption(self):
        manifest = parse_manifest(
            encode_bts(["https://cdn/a"], encryption="NONE"), MANIFEST_MIME_BTS
        )
        assert manifest.encryption_type == "NONE"


class TestDashManifest:
    def test_expands_number_placeholder(self):
        # Two explicit segments plus one with r="2" -> 1 + 1 + (1 + 2) = 5 urls.
        # DASH segment numbering starts at 1 unless startNumber says otherwise.
        manifest = parse_manifest(
            encode_dash(
                "https://cdn/seg$Number$.mp4", "mp4a.40.2", [None, None, 2]
            ),
            MANIFEST_MIME_DASH,
        )
        assert len(manifest.urls) == 5
        assert manifest.urls[0] == "https://cdn/seg1.mp4"
        assert manifest.urls[-1] == "https://cdn/seg5.mp4"

    def test_respects_start_number(self):
        manifest = parse_manifest(
            encode_dash(
                "https://cdn/seg$Number$.mp4", "mp4a.40.2", [None, None],
                start_number=7,
            ),
            MANIFEST_MIME_DASH,
        )
        assert manifest.urls == [
            "https://cdn/seg7.mp4",
            "https://cdn/seg8.mp4",
        ]

    def test_unterminated_initialization_attribute(self):
        # Regression for real Tidal manifests: the initialization attribute has
        # no closing quote and the base64 payload runs into </AdaptationSet>,
        # which no conforming XML parser accepts.
        manifest = parse_manifest(encode_broken_dash(), MANIFEST_MIME_DASH)
        assert manifest.codecs == "flac"
        assert manifest.encryption_type == "NONE"
        assert len(manifest.urls) == 1
        assert manifest.urls[0].startswith(
            "https://sp-ad-cf.audio.tidal.com/mediatracks/"
        )
        # XML entities inside the URL must be decoded back to raw characters.
        assert "&amp;Signature=" not in manifest.urls[0]
        assert "&Signature=" in manifest.urls[0]

    def test_representation_without_period_wrapper(self):
        # Real manifests place Representation directly under MPD.
        manifest = parse_manifest(encode_dash_flat(), MANIFEST_MIME_DASH)
        assert manifest.codecs == "flac"
        assert manifest.urls == ["https://cdn/whole.flac"]

    def test_single_segment(self):
        manifest = parse_manifest(
            encode_dash("https://cdn/only.mp4", "flac", [None]),
            MANIFEST_MIME_DASH,
        )
        assert manifest.urls == ["https://cdn/only.mp4"]
        assert manifest.file_extension == ".flac"

    def test_rejects_negative_repeat_count(self):
        manifest = encode_dash(
            "https://cdn/seg$Number$.mp4", "mp4a.40.2", [-5]
        )
        with pytest.raises(ManifestError, match="negative repeat counts"):
            parse_manifest(manifest, MANIFEST_MIME_DASH)


class TestValidation:
    def test_rejects_unknown_mime(self):
        manifest = encode_bts(["https://cdn/a"])
        with pytest.raises(ManifestError, match="Unsupported manifest mime type"):
            parse_manifest(manifest, "application/octet-stream")

    def test_rejects_empty_manifest(self):
        with pytest.raises(ManifestError, match="empty"):
            parse_manifest("", MANIFEST_MIME_BTS)

    def test_rejects_bad_base64(self):
        with pytest.raises(ManifestError, match="base64"):
            parse_manifest("!!!not-base64!!!", MANIFEST_MIME_BTS)

    def test_rejects_bts_with_invalid_json(self):
        manifest = b64encode(b"not json").decode()
        with pytest.raises(ManifestError, match="not valid JSON"):
            parse_manifest(manifest, MANIFEST_MIME_BTS)


class TestQualityNormalization:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            # Tidal's native names win, matching the existing /track/ endpoint.
            ("LOW", "LOW"),
            ("HIGH", "HIGH"),
            ("LOSSLESS", "LOSSLESS"),
            ("HI_RES_LOSSLESS", "HI_RES_LOSSLESS"),
            ("hires_lossless", "HI_RES_LOSSLESS"),
            ("lossless", "LOSSLESS"),
            # tiddl aliases that do not collide with a native name.
            ("low", "LOW"),
            ("normal", "HIGH"),
            ("max", "HI_RES_LOSSLESS"),
            ("MAX", "HI_RES_LOSSLESS"),
        ],
    )
    def test_maps_aliases(self, raw, expected):
        assert normalize_quality(raw) == expected

    def test_tidal_high_wins_over_tiddl_high_alias(self):
        # tiddl's "high" alias means LOSSLESS, but Tidal has a real HIGH
        # quality (320 kbps AAC). Because the rest of this API speaks Tidal's
        # vocabulary, the native name takes precedence; use "lossless" for the
        # lossless tier.
        assert normalize_quality("high") == "HIGH"
        assert normalize_quality("lossless") == "LOSSLESS"

    def test_rejects_unknown(self):
        with pytest.raises(ValueError, match="Unsupported quality"):
            normalize_quality("ultra")


class TestPathSanitisation:
    def test_strips_traversal(self):
        assert ".." not in sanitize_component("../../etc/passwd")

    def test_strips_illegal_chars(self):
        assert "/" not in sanitize_component("AC/DC")
        assert ":" not in sanitize_component("Artist: Name")

    def test_empty_falls_back(self):
        assert sanitize_component("", fallback="Unknown") == "Unknown"
        assert sanitize_component(None) == "Unknown"

    def test_reserved_windows_names_escaped(self):
        assert sanitize_component("CON") == "CON_"
        assert sanitize_component("nul") == "nul_"

    def test_traversal_in_title_cannot_escape_root(self, tmp_path):
        path = build_track_path(
            tmp_path,
            title="../../../../etc/passwd",
            artist="Artist",
            album="Album",
            number=1,
            extension=".flac",
        )
        # The sanitised title must not introduce directory traversal.
        assert ".." not in str(path)


class TestPathBuilding:
    def test_builds_nested_path(self, tmp_path):
        path = build_track_path(
            tmp_path,
            title="One More Time",
            artist="Daft Punk",
            album="Discovery",
            number=1,
            extension=".flac",
        )
        assert path.suffix == ".flac"
        assert path.parent.name == "Discovery"
        assert "Daft Punk" in str(path)

    def test_custom_template(self, tmp_path):
        path = build_track_path(
            tmp_path,
            template="{artist}/{title}",
            title="Get Lucky",
            artist="Daft Punk",
            album="Random Access",
            number=2,
            extension=".m4a",
        )
        assert path.parent.name == "Daft Punk"
        assert path.stem == "Get Lucky"

    def test_title_with_dots_is_not_truncated(self, tmp_path):
        # Regression: building the name with Path.with_suffix() treated
        # ". One More Time" as a suffix and produced "01.flac", discarding the
        # title. Only the real extension should be appended.
        path = build_track_path(
            tmp_path,
            title="One More Time",
            artist="Daft Punk",
            album="Discovery",
            number=1,
            extension=".flac",
        )
        assert path.name == "01. One More Time.flac"

    def test_title_containing_multiple_dots(self, tmp_path):
        path = build_track_path(
            tmp_path,
            title="Pt. 2 feat. X (Remastered 2011)",
            artist="A",
            album="B",
            number=3,
            extension=".m4a",
        )
        assert path.name == "03. Pt. 2 feat. X (Remastered 2011).m4a"

    def test_extension_is_appended_only_once(self, tmp_path):
        path = build_track_path(
            tmp_path,
            title="Track",
            artist="A",
            album="B",
            number=1,
            extension=".flac",
        )
        assert path.suffix == ".flac"
        assert not path.name.endswith(".flac.flac")
