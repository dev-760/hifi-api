"""Local end-to-end download test against a fake Tidal + fake CDN.

This exercises the *real* code path end to end - genuine HTTP requests, genuine
manifest parsing, genuine file writes - without contacting Tidal or using any
credentials. Nothing here can put an account at risk, so it is safe to run
repeatedly.

A small FastAPI app stands in for Tidal's API and its CDN. The download
endpoints are then pointed at it, and a real track is "downloaded" to a
temporary directory.

Run with:
    python tests/local_e2e.py
"""

from __future__ import annotations

import base64
import json
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import uvicorn  # noqa: E402
from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import JSONResponse, Response  # noqa: E402

import main  # noqa: E402
import download.service as dl_service  # noqa: E402

# --- Fake upstream ----------------------------------------------------------

FAKE_PORT = 8899
FAKE_BASE = f"http://127.0.0.1:{FAKE_PORT}"

# Segment payloads. Two distinct blobs so concatenation is observable.
SEG_A = b"A" * 4096
SEG_B = b"B" * 2048

fake = FastAPI()
HITS: dict[str, int] = {}


def _bts(codecs: str, urls: list[str], encryption: str = "NONE") -> str:
    payload = {
        "mimeType": "audio/mp4",
        "codecs": codecs,
        "encryptionType": encryption,
        "urls": urls,
    }
    return base64.b64encode(json.dumps(payload).encode()).decode()


def _dash(template: str, codecs: str, segments: int) -> str:
    parts = "".join(f'<S d="1000"/>' for _ in range(segments))
    xml = (
        '<MPD xmlns="urn:mpeg:dash:schema:mpd:2011" type="static"><Period>'
        '<AdaptationSet mimeType="audio/mp4">'
        f'<Representation codecs="{codecs}">'
        f'<SegmentTemplate media="{template}">'
        f"<SegmentTimeline>{parts}</SegmentTimeline>"
        "</SegmentTemplate></Representation></AdaptationSet></Period></MPD>"
    )
    return base64.b64encode(xml.encode()).decode()


@fake.get("/v1/tracks/{track_id}/playbackinfopaywall")
async def playback_info(track_id: int, request: Request):
    """Stand-in for Tidal's playbackinfopaywall endpoint."""
    HITS["playbackinfo"] = HITS.get("playbackinfo", 0) + 1

    auth = request.headers.get("authorization", "")
    if not auth.startswith("Bearer "):
        return JSONResponse({"detail": "missing bearer"}, status_code=401)

    quality = request.query_params.get("audioquality", "")

    # HI_RES_LOSSLESS is served as FLAC-in-MP4 via DASH, like the real service.
    if quality == "HI_RES_LOSSLESS":
        return {
            "manifest": _dash(
                f"{FAKE_BASE}/cdn/seg$Number$.bin", "flac", segments=3
            ),
            "manifestMimeType": "application/dash+xml",
            "audioQuality": quality,
            "audioMode": "STEREO",
            "bitDepth": 24,
            "sampleRate": 192000,
        }

    return {
        "manifest": _bts(
            "flac", [f"{FAKE_BASE}/cdn/a.bin", f"{FAKE_BASE}/cdn/b.bin"]
        ),
        "manifestMimeType": "application/vnd.tidal.bts",
        "audioQuality": quality,
        "audioMode": "STEREO",
        "bitDepth": 16,
        "sampleRate": 44100,
    }


@fake.get("/cdn/a.bin")
async def cdn_a():
    HITS["cdn_a"] = HITS.get("cdn_a", 0) + 1
    return Response(SEG_A, media_type="application/octet-stream")


@fake.get("/cdn/b.bin")
async def cdn_b():
    HITS["cdn_b"] = HITS.get("cdn_b", 0) + 1
    return Response(SEG_B, media_type="application/octet-stream")


@fake.get("/cdn/seg{number}.bin")
async def cdn_seg(number: int):
    HITS[f"cdn_seg{number}"] = HITS.get(f"cdn_seg{number}", 0) + 1
    return Response(bytes([48 + number]) * 1024, media_type="application/octet-stream")


@fake.get("/v1/tracks/{track_id}/")
async def track_metadata(track_id: int):
    """Catalog metadata endpoint used to derive the filename."""
    HITS["metadata"] = HITS.get("metadata", 0) + 1
    return {
        "id": track_id,
        "title": "One More Time",
        "trackNumber": 1,
        "isrc": "FR1234567890",
        "artists": [{"name": "Daft Punk", "type": "MAIN"}],
        "album": {"id": 10, "title": "Discovery"},
    }


def start_fake_server() -> uvicorn.Server:
    config = uvicorn.Config(fake, host="127.0.0.1",
                            port=FAKE_PORT, log_level="error")
    server = uvicorn.Server(config)
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for the socket to accept connections.
    import socket

    for _ in range(100):
        try:
            with socket.create_connection(("127.0.0.1", FAKE_PORT), timeout=0.2):
                return server
        except OSError:
            time.sleep(0.1)
    raise RuntimeError("fake upstream did not start")


# --- Test body --------------------------------------------------------------


def main_test() -> int:
    start_fake_server()
    tmp = Path(tempfile.mkdtemp(prefix="hifi-e2e-"))
    failures: list[str] = []

    def check(label: str, condition: bool, detail: str = "") -> None:
        mark = "PASS" if condition else "FAIL"
        print(f"  [{mark}] {label}" + (f" - {detail}" if detail else ""))
        if not condition:
            failures.append(label)

    try:
        # Point the download path at the fake upstream and enable downloads.
        main.ENABLE_DOWNLOADS = True
        main.IS_SERVERLESS = False
        main.DOWNLOAD_DIR = str(tmp)
        main._download_root = None
        dl_service.PLAYBACK_INFO_URL = f"{FAKE_BASE}/v1/tracks/{{track_id}}/playbackinfopaywall"

        async def stub_token(cred=None, force_refresh=False):
            return "fake-token", {"access_token": "fake", "expires_at": 9e9}

        async def stub_metadata(track_id: int):
            import httpx

            async with httpx.AsyncClient() as client:
                resp = await client.get(f"{FAKE_BASE}/v1/tracks/{track_id}/")
                return resp.json()

        main.get_tidal_token_for_cred = stub_token
        main._track_metadata_cached = stub_metadata

        from fastapi.testclient import TestClient

        with TestClient(main.app) as client:
            print("\n1. Resolve (BTS manifest, LOSSLESS)")
            r = client.get("/download/resolve/?id=194567102&quality=LOSSLESS")
            check("resolve returns 200", r.status_code ==
                  200, f"got {r.status_code}")
            if r.status_code == 200:
                body = r.json()
                check("two segments", body["urlCount"]
                      == 2, str(body["urlCount"]))
                check("flac extension", body["fileExtension"] == ".flac")
                check("encryption NONE", body["encryptionType"] == "NONE")
                check(
                    "bit depth parsed",
                    body["bitDepth"] == 16,
                    str(body["bitDepth"]),
                )

            print("\n2. Resolve (DASH manifest, HI_RES_LOSSLESS)")
            r = client.get("/download/resolve/?id=194567102&quality=max")
            check("resolve returns 200", r.status_code ==
                  200, f"got {r.status_code}")
            if r.status_code == 200:
                body = r.json()
                check("three segments",
                      body["urlCount"] == 3, str(body["urlCount"]))
                check("m4a extension", body["fileExtension"] == ".m4a")
                check("needs extraction", body["needsFlacExtraction"] is True)
                check("24-bit/192kHz", body["bitDepth"]
                      == 24 and body["sampleRate"] == 192000)

            print("\n3. Download to disk (LOSSLESS -> .flac)")
            r = client.post("/download/track/?id=194567102&quality=LOSSLESS")
            check("download returns 200", r.status_code ==
                  200, f"got {r.status_code} {r.text[:200]}")
            if r.status_code == 200:
                body = r.json()
                written = Path(body["path"])
                check("file exists", written.exists(), str(written))
                check("suffix .flac", written.suffix == ".flac", written.suffix)
                check(
                    "size matches segments",
                    written.stat().st_size == len(SEG_A) + len(SEG_B),
                    f"{written.stat().st_size} vs {len(SEG_A) + len(SEG_B)}",
                )
                check(
                    "path template applied",
                    written.parent.name == "Discovery"
                    and written.parent.parent.name == "Daft Punk",
                    str(written.parent),
                )
                check("filename numbered", written.name.startswith(
                    "01. "), written.name)
                check(
                    "no .part left behind",
                    not list(written.parent.glob("*.part")),
                )

            print("\n4. Skip existing")
            r = client.post("/download/track/?id=194567102&quality=LOSSLESS")
            check("second call reports exists", r.json().get(
                "status") == "exists", r.text[:120])
            check("cdn not re-fetched", HITS.get("cdn_a", 0)
                  == 1, f"cdn_a hits={HITS.get('cdn_a')}")

            print("\n5. HI_RES download (DASH -> FLAC-in-MP4)")
            r = client.post(
                "/download/track/?id=194567102&quality=HI_RES_LOSSLESS")
            check("hires returns 200", r.status_code == 200,
                  f"got {r.status_code} {r.text[:200]}")
            if r.status_code == 200:
                written = Path(r.json()["path"])
                check("hires file exists", written.exists(), str(written))
                check(
                    "three dash segments fetched",
                    HITS.get("cdn_seg0", 0) >= 1 and HITS.get(
                        "cdn_seg2", 0) >= 1,
                    f"hits={{k: v for k, v in HITS.items() if 'seg' in k} }",
                )

            print("\n6. Validation and gating")
            check(
                "bad quality -> 422",
                client.get(
                    "/download/resolve/?id=1&quality=ultra").status_code == 422,
            )
            main.ENABLE_DOWNLOADS = False
            check(
                "downloads disabled -> 503",
                client.post("/download/track/?id=1").status_code == 503,
            )
            check(
                "resolve still works when disabled",
                client.get("/download/resolve/?id=1").status_code == 200,
            )
            main.ENABLE_DOWNLOADS = True
            main.IS_SERVERLESS = True
            check(
                "serverless download -> 501",
                client.post("/download/track/?id=1").status_code == 501,
            )
            main.IS_SERVERLESS = False

            print("\n7. Upstream call counts")
            check(
                "metadata fetched per download",
                HITS.get("metadata", 0) >= 2,
                f"metadata hits={HITS.get('metadata')}",
            )

        print("\n" + "=" * 58)
        if failures:
            print(f"FAILED: {len(failures)} check(s): {failures}")
            return 1
        print("All local end-to-end checks passed.")
        return 0

    finally:
        shutil.rmtree(tmp, ignore_errors=True)


if __name__ == "__main__":
    raise SystemExit(main_test())
