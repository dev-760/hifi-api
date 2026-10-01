"""End-to-end checks for the download endpoints using stubbed dependencies.

No Tidal credentials and no network access are required: the token helper,
HTTP client, manifest fetch and CDN transfer are all replaced.

Run with:
    python -m pytest tests/test_download_api.py -q
"""

from __future__ import annotations

import asyncio
import base64
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import main  # noqa: E402
from download.manifest import MANIFEST_MIME_BTS, parse_manifest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

TRACK_PAYLOAD = {
    "id": 1,
    "title": "One More Time",
    "trackNumber": 1,
    "isrc": "FR1234567890",
    "artists": [{"name": "Daft Punk", "type": "MAIN"}],
    "album": {"id": 10, "title": "Discovery"},
}


def bts_manifest(codecs: str = "flac") -> str:
    payload = {
        "mimeType": "audio/mp4",
        "codecs": codecs,
        "encryptionType": "NONE",
        "urls": ["https://cdn.example/seg0", "https://cdn.example/seg1"],
    }
    return base64.b64encode(json.dumps(payload).encode()).decode()


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A TestClient with downloads enabled and every network call stubbed."""
    monkeypatch.setattr(main, "ENABLE_DOWNLOADS", True, raising=False)
    monkeypatch.setattr(main, "IS_SERVERLESS", False, raising=False)
    monkeypatch.setattr(main, "DOWNLOAD_DIR", str(tmp_path), raising=False)
    monkeypatch.setattr(main, "_download_root", None, raising=False)

    async def fake_token(cred=None, force_refresh=False):
        return "stub-token", {"access_token": "stub", "expires_at": 9e9}

    async def fake_client():
        return object()

    async def fake_stream(client, token, track_id, quality, **kwargs):
        return parse_manifest(
            bts_manifest(),
            MANIFEST_MIME_BTS,
            audio_quality=quality,
        )

    async def fake_segments(client, urls, **kwargs):
        for _ in urls:
            yield b"audio-bytes"

    async def fake_metadata(track_id):
        return dict(TRACK_PAYLOAD)

    monkeypatch.setattr(main, "get_tidal_token_for_cred", fake_token)
    monkeypatch.setattr(main, "get_http_client", fake_client)
    monkeypatch.setattr(main, "fetch_track_stream", fake_stream)
    monkeypatch.setattr(main, "download_segments", fake_segments)
    monkeypatch.setattr(main, "_track_metadata_cached", fake_metadata)

    with TestClient(main.app) as test_client:
        yield test_client


class TestResolveEndpoint:
    def test_resolve_returns_urls_without_writing(self, client, tmp_path):
        response = client.get("/download/resolve/?id=1")
        assert response.status_code == 200

        body = response.json()
        assert body["trackId"] == 1
        assert body["urls"] == [
            "https://cdn.example/seg0", "https://cdn.example/seg1"]
        assert body["urlCount"] == 2
        assert body["encryptionType"] == "NONE"
        # Resolve must never touch the filesystem.
        assert list(tmp_path.iterdir()) == []

    def test_resolve_works_when_downloads_disabled(self, client, monkeypatch):
        # The resolve endpoint is stateless, so it stays available even when
        # disk downloads are switched off.
        monkeypatch.setattr(main, "ENABLE_DOWNLOADS", False, raising=False)
        response = client.get("/download/resolve/?id=1")
        assert response.status_code == 200

    def test_resolve_rejects_bad_quality(self, client):
        response = client.get("/download/resolve/?id=1&quality=ultra")
        assert response.status_code == 422
        assert "Unsupported quality" in response.json()["detail"]

    def test_resolve_accepts_alias_quality(self, client):
        response = client.get("/download/resolve/?id=1&quality=max")
        assert response.status_code == 200
        assert response.json()["requestedQuality"] == "HI_RES_LOSSLESS"


class TestDownloadEndpoint:
    def test_download_writes_file(self, client, tmp_path):
        response = client.post("/download/track/?id=1")
        assert response.status_code == 200

        body = response.json()
        assert body["status"] == "downloaded"
        assert body["bytes"] == len(b"audio-bytes") * 2

        written = Path(body["path"])
        assert written.exists()
        assert written.read_bytes() == b"audio-bytes" * 2
        # Template should place it under Artist/Album.
        assert written.parent.name == "Discovery"

    def test_skip_existing_does_not_rewrite(self, client, tmp_path):
        first = client.post("/download/track/?id=1").json()
        second = client.post("/download/track/?id=1").json()

        assert first["status"] == "downloaded"
        assert second["status"] == "exists"
        assert second["path"] == first["path"]

    def test_disabled_downloads_returns_503(self, client, monkeypatch):
        monkeypatch.setattr(main, "ENABLE_DOWNLOADS", False, raising=False)
        response = client.post("/download/track/?id=1")
        assert response.status_code == 503
        assert "ENABLE_DOWNLOADS" in response.json()["detail"]

    def test_serverless_returns_501(self, client, monkeypatch):
        monkeypatch.setattr(main, "IS_SERVERLESS", True, raising=False)
        response = client.post("/download/track/?id=1")
        assert response.status_code == 501
        assert "serverless" in response.json()["detail"]

    def test_path_traversal_in_title_is_contained(self, client, monkeypatch, tmp_path):
        async def hostile_metadata(track_id):
            payload = dict(TRACK_PAYLOAD)
            payload["title"] = "../../../../etc/passwd"
            payload["album"] = {"id": 10, "title": "Album"}
            return payload

        monkeypatch.setattr(main, "_track_metadata_cached", hostile_metadata)

        body = client.post("/download/track/?id=1").json()
        written = Path(body["path"])
        assert written.exists()
        assert tmp_path.resolve() in written.resolve().parents


class TestJobPolling:
    def test_unknown_request_returns_404(self, client):
        assert client.get(
            "/download/requests/does-not-exist").status_code == 404
