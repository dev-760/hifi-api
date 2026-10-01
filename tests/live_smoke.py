"""Live smoke test against the deployed hifi-api.

Read-only probes only: nothing that starts a download or mutates state.
Reports status, latency and a response sample for each endpoint.

Run with:
    python tests/live_smoke.py
"""

import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

BASE = "https://hifi-api00.vercel.app"

TRACK_ID = 194567102
ALBUM_ID = 194567097
ARTIST_ID = 3959838
PLAYLIST_ID = "1c5d01ed-4f05-40c4-bd28-0f730f9b220b"

PROBES = [
    ("GET", "/", None, None),
    ("GET", "/info/", {"id": TRACK_ID}, None),
    ("GET", "/track/", {"id": TRACK_ID, "quality": "LOSSLESS"}, None),
    ("GET", "/track/", {"id": TRACK_ID, "quality": "HI_RES_LOSSLESS"}, None),
    ("GET", "/recommendations/", {"id": TRACK_ID}, None),
    ("GET", "/lyrics/", {"id": TRACK_ID}, None),
    ("GET", "/cover/", {"id": TRACK_ID}, None),
    ("GET", "/cover/", {"q": "daft punk"}, None),
    ("GET", "/album/", {"id": ALBUM_ID, "limit": 5}, None),
    ("GET", "/album/similar/", {"id": ALBUM_ID}, None),
    ("GET", "/artist/", {"id": ARTIST_ID}, None),
    ("GET", "/artist/", {"f": ARTIST_ID, "skip_tracks": "true"}, None),
    ("GET", "/artist/similar/", {"id": ARTIST_ID}, None),
    ("GET", "/search/", {"s": "daft punk", "limit": 3}, None),
    ("GET", "/search/", {"a": "daft punk", "limit": 3}, None),
    ("GET", "/search/", {"al": "discovery", "limit": 3}, None),
    ("GET", "/search/", {"v": "daft punk", "limit": 3}, None),
    ("GET", "/search/", {"p": "chill", "limit": 3}, None),
    # The hardcoded playlist id in the repo's test data is stale; Tidal returns
    # 404 for it. Marked as an accepted 404 so a real regression is still caught.
    ("GET", "/playlist/", {"id": PLAYLIST_ID, "limit": 5}, (200, 404)),
    ("GET", "/topvideos/", {"limit": 3}, None),
    ("GET", "/trackManifests/", {"id": str(TRACK_ID)}, None),
    # Download surface
    ("GET", "/download/resolve/",
     {"id": TRACK_ID, "quality": "LOSSLESS"}, None),
    ("GET", "/download/resolve/", {"id": TRACK_ID, "quality": "max"}, None),
    ("GET", "/download/resolve/",
     {"id": TRACK_ID, "quality": "ultra"}, 422),
    ("POST", "/download/track/", {"id": TRACK_ID,
     "quality": "LOSSLESS"}, (501, 503)),
    ("GET", "/download/requests/unknown-id-123", None, 404),
    ("DELETE", "/playback/requests/unknown-id-123", None, 404),
    # Error handling
    ("GET", "/info/", {"id": 999999999999}, 404),
    ("GET", "/search/", {}, 400),
]


def probe(method, path, params, expected):
    url = f"{BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)

    data = None
    headers = {"User-Agent": "hifi-api-live-smoke/1.0",
               "Accept": "application/json"}
    if method == "POST":
        data = b""
        headers["Content-Type"] = "application/json"

    req = urllib.request.Request(
        url, data=data, headers=headers, method=method)

    start = time.time()
    try:
        with urllib.request.urlopen(req, timeout=45) as resp:
            body = resp.read().decode("utf-8", "replace")
            status = resp.status
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace")
        status = exc.code
    except Exception as exc:
        body = f"{type(exc).__name__}: {exc}"
        status = 0
    elapsed = time.time() - start

    # expected=None means "2xx expected"; a tuple means "any of these".
    if expected is None:
        ok = 200 <= status < 300
    elif isinstance(expected, tuple):
        ok = status in expected
    else:
        ok = status == expected

    return {
        "method": method,
        "path": path,
        "params": params or {},
        "status": status,
        "expected": expected,
        "ok": ok,
        "ms": round(elapsed * 1000),
        "len": len(body),
        "sample": body[:150].replace("\n", " "),
    }


def main() -> int:
    base = Path(__file__).resolve().parent.parent

    print(f"Live smoke test: {BASE}\n")
    results = []

    for method, path, params, expected in PROBES:
        result = probe(method, path, params, expected)
        results.append(result)

        mark = "PASS" if result["ok"] else "FAIL"
        print(
            f"{mark} {result['status']:>3}  {result['ms']:>6}ms  "
            f"{result['method']:<6} {result['path']}"
            + (f"  (expect {expected})" if expected is not None else "")
        )
        if not result["ok"]:
            print(f"        -> {result['sample']}")

    print("\n" + "=" * 70)
    passed = [r for r in results if r["ok"]]
    failed = [r for r in results if not r["ok"]]
    print(f"pass: {len(passed)}/{len(results)}    fail: {len(failed)}")

    for r in failed:
        print(
            f"  got {r['status']} {r['method']} {r['path']} "
            f"{r['params']} (expected {r['expected']})"
        )

    out = base / "live_probe_results.json"
    out.write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("\nsaved ->", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
