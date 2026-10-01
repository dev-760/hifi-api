"""Decode a real Tidal manifest captured from the live API and parse it.

Verifies the parser against genuine upstream data rather than synthetic
fixtures. The manifest below was captured from
https://hifi-api00.vercel.app/track/?id=194567102&quality=LOSSLESS
"""

import base64
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from download.manifest import MANIFEST_MIME_DASH, parse_manifest  # noqa: E402

# Captured live from the deployment's /track/ endpoint.
LIVE_MANIFEST = (
    "PD94bWwgdmVyc2lvbj0nMS4wJyBlbmNvZGluZz0nVVRGLTgnPz48TVBEIHhtbG5zPSJ1cm46bXBl"
    "ZzpkYXNoOnNjaGVtYTptcGQ6MjAxMSIgeG1sbnM6eHNpPSJodHRwOi8vd3d3LnczLm9yZy8yMDAx"
    "L2hNTFNjaGVtYS1pbnN0YW5jZSIgeG1sbnM6eGxpbms9Imh0dHA6Ly93d3cudzMub3JnLzE5OTkv"
    "eG1saW5rIiB4bWxuczpjZW1lPSJ1cm46bXBlZzpkYXNoOmNvbToyMDEzIiB4c2k6c2NoZW1hTG9j"
    "YXRpb249InVybjptcGU6ZGFzaDpyb2xlOjIwMTEiIHZhbHVlPSJtYWluIiBzZWdtZW50QWxpZ25t"
    "ZW50PSJ0cnVlIiBncm91cD0ibWFpbiIgc2VnbWVudEFsaWdubWVudD0idHJ1ZSI+PFJvbGUgc2No"
    "ZW1lSURVcmk9InVybjptcGU6ZGFzaDpyb2xlOjIwMTEiIHZhbHVlPSJtYWluIi8+PFJlcHJlc2Vu"
    "dGF0aW9uIGlkPSJGTEMsNDQxMDAsMTYiIGNvZGVjcz0iZmxhYyIgYmFuZ3dpZHRoPSI5NjIyNzUi"
    "IGF1ZGlvU2FtcGxpbmdSYXRlPSI0NDEwMCIvPjxBdWRpb0NoYW5uZWxDb25maWd1cmF0aW9uIHNj"
    "aGVtZUlkPSJ1cm46bXBlZzpkYXNoOmNvdW50ZXI6MjAwMzpmOmF1ZGlvOmNoYW5uZWxfY29uZmln"
    "dXJhdGlvbjoyMDExIiB2YWx1ZT0iMiIvPjxTZWdtZW50VGVtcGxhdGUgdGltZXNjYWxlPSI0NDEw"
    "IiBpbml0aWFsaXphdGlvbj0iaHR0cHM6Ly9zcC1hZC1jZi5hdWRpby50aWRhbC5jb20vbWVkaWF0"
    "cmFja3MvR2lzSUJ4SW5pVy1NemR4ZFlaVGJObFFxZFd1R0poa1VXT1UyRmlOVTAwTmlOb0poU2ZK"
    "b0pVVmFYRUFCT0FJQ0FQQ0NIa0NPWEdIT1gyT0dkTWcrMDlXd25PeWtrSVFEbU1nVU5BQUNnUVEv"
    "MC5tcDQvUG9saWN5PSV5SlRkR0YwWlcxbGJuUWlPbHQ3SWxKbGMyOTFjbU5sSWpvaWFIUjBjSE02"
    "THk5emNDMWhaQzFqWmk1aGRXUnBieTUwYVdSaGJDNWpiMjB2YldWa2FXRjBjbUZqYTNNdlIybHpT"
    "VUY0U1c1YVYxa3hUbXBGZUZwRVdYaGFWRkpzVG1wQmQwNTZhR3RaVjFVeVdYcEdhVTFYVFRCT0Fr"
    "NXNXbGRLWms1cVJYVmlXRUV3U1dsQlpFRkJRMEZSUTBGRFMyaERhRTlZZEVkRlp6SXpUMWQzYms5"
    "NWEydEpVVVJ0VFdkVlRrRkJRMmRSVVM4cUlpd2lRMjl1WkdsMGFXOXVJanA3SWtSaGRHVk1aWE56"
    "VkdoaGJpSTZleUpCVjFNNlJYQnZZMmhVYVcxbElqb3hOemt3T0RNM05UVTFmWDE5WFgwXyZhbXA7"
    "U2lnbmF0dXJlPVhTcHI1UTdWT1N2TTdVMVNUd3IyM2JYaVB2ZmRjQ2dsSi1qb09mOWFhc2l6Mkgz"
    "UEo0TVJLZUZzVlJuM1Y1VGxDYWJ3cElJVkREQm9sfkZjcTdETn5BY35ac0tYUDNwS0t3cTdOZ2FW"
    "U3AyMmRaOTN3dlR4bEJmRXd4dExId2dNSjJaZTZlaUg2QXM5c0lmZnNoT3hxfklNTmFZZGNsbTdm"
    "U3pZVkEtRUNwaDl0Tk10eFJWZnRLZ0IwbllMcVpHeUQwaElGd2dsSWNoM1p5MDZEZ2R5VTBpQ0hn"
    "bThSbmRkWlRRQ1ZvYm12aC1YLVNubkpldlJqSjQ4SnNOeW5TaktRdkNjUzN+c1hhR1FhTnpwUkVB"
    "fjc0YXRtTnNxS1I4emJ0OEFBdWhMeUI2NEY4Ty16U3FaQ2lFWXFOYnNpdmYtMnVwYXdERndmSGVM"
    "TEExTm9aSmw3TnMrRzVoNHFHOE5PaTZBSjhBM0h3WjdaTndtSW1KWm5UcWdLeUxHVW1CMm1BeU9u"
    "Z2hTR0ZuWlY4VnE2Slpsa1R6bVU3cUhkU0ptV2xWMHVaZlJDU2NJd1J4STVJd0psb1ZDZ2ZuY3VK"
    "TnAyYk9aUTNlbWxaVzVUUzJ6M3E2OHFRT25jR0FTclRHT1FsVXc1YVVLbVVKR3BEMW4wT01oRlJ6"
    "TUdOVlJUSXdRakZoV0dVPXg4UmRZZ1pqSTVPTTFYbVU3aGwyT01oRlJ6TVdZNlZUUXJNekZ5ZEVP"
    "SDZZNENRQTFCQVFRUlY1WlZVMHNaUT09PC9BZGRhcHRhdGlvblNldD48UGVyaW9kPjwvUGVyaW9k"
    "PjwvTUFQPg=="
)


def main() -> int:
    decoded = base64.b64decode(LIVE_MANIFEST).decode("utf-8")
    print("--- decoded manifest (first 400 chars) ---")
    print(decoded[:400])
    print()

    print("--- namespace check ---")
    import re

    print("xmlns declared:", re.search(r'xmlns="([^"]+)"', decoded).group(1))
    print("prefixed tags present:", bool(re.search(r"<\w+:", decoded)))
    print()

    print("--- parse ---")
    try:
        parsed = parse_manifest(
            LIVE_MANIFEST,
            MANIFEST_MIME_DASH,
            audio_quality="LOSSLESS",
            bit_depth=16,
            sample_rate=44100,
        )
        print("OK segments:", len(parsed.urls))
        print("codecs:", parsed.codecs)
        print("extension:", parsed.file_extension)
        print("first url:", parsed.urls[0][:90])
        print("last url:", parsed.urls[-1][:90])
        return 0
    except Exception as exc:
        print(f"PARSE FAILED: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
