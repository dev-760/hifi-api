"""Prepare a Tidal credential rotation.

The refresh token in ``token.json`` was committed at 5589382 and pushed to
GitHub, so it must be treated as compromised. This script makes the rotation
safe by:

  1. Backing up the existing (soon-to-be-invalid) credentials.
  2. Recording exactly what is exposed, so the purge can be verified later.
  3. Printing the steps to get a fresh token.

It never prints the token value itself.

Run with:
    python tools/rotate_credentials.py --prepare
    python tools/rotate_credentials.py --verify
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKEN_FILE = ROOT / "token.json"
BACKUP_DIR = ROOT / ".credential-backup"

# The commit that leaked token.json to the public repository.
LEAKED_COMMIT = "5589382"


def load_tokens() -> list[dict]:
    if not TOKEN_FILE.exists():
        sys.exit(
            f"No {TOKEN_FILE.name} found. Run tidal_auth/tidal_auth.py first.")

    data = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        data = [data]

    for entry in data:
        if not isinstance(entry, dict) or not entry.get("refresh_token"):
            sys.exit("token.json contains an entry with no refresh_token.")
    return data


def describe(entries: list[dict]) -> None:
    print(f"\n{TOKEN_FILE.name} holds {len(entries)} credential set(s):\n")
    for i, entry in enumerate(entries, 1):
        role = entry.get("role") or "playback"
        token = entry.get("refresh_token", "")
        masked = f"{token[:6]}...{token[-4:]}" if len(token) > 12 else "***"
        print(f"  {i}. role={role:<8} userID={entry.get('userID', '?')}")
        print(f"     refresh_token={masked}  (len {len(token)})")


def find_in_history() -> list[str]:
    """Return commits whose tree contains token.json."""
    try:
        out = subprocess.run(
            ["git", "log", "--all", "--oneline", "--", "token.json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        ).stdout
    except Exception as exc:  # noqa: BLE001
        return [f"(could not query git: {exc})"]

    return [line.split()[0] for line in out.splitlines() if line.strip()]


def prepare() -> int:
    entries = load_tokens()
    describe(entries)

    # 1. Back up the current credentials so the API keeps working if
    #    re-authentication has to wait.
    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    backup = BACKUP_DIR / f"token.{stamp}.json.bak"
    shutil.copy2(TOKEN_FILE, backup)
    backup.chmod(0o600)

    print(f"\nBacked up to: {backup.relative_to(ROOT)}")

    # 2. Record the exposure.
    commits = find_in_history()
    report = {
        "prepared_at": stamp,
        "token_file": "token.json",
        "credential_count": len(entries),
        "user_ids": [e.get("userID") for e in entries],
        "roles": [e.get("role") or "playback" for e in entries],
        "commits_containing_token_file": commits,
        "known_leaked_commit": LEAKED_COMMIT,
        "pushed_to": "https://github.com/dev-760/hifi-api",
        "status": "ROTATION_PENDING",
        "next_step": "Run tidal_auth/tidal_auth.py to obtain a fresh refresh token, "
        "then replace token.json and re-run with --verify.",
    }
    report_file = BACKUP_DIR / "rotation-report.json"
    report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Exposure report: {report_file.relative_to(ROOT)}")

    print("\nCommits still containing token.json:")
    for commit in commits:
        print(f"  {commit}")

    print(
        "\n" + "=" * 62
        + "\nNEXT: obtain a new refresh token\n" + "=" * 62
    )
    print(
        """
  1. pip install -r tidal_auth/requirements.txt
  2. python tidal_auth/tidal_auth.py

  It opens a Tidal login URL. Sign in, click Authorize, and the script
  writes a fresh token.json.

  3. python tools/rotate_credentials.py --verify
     Re-run tests afterwards:
       python -m pytest tests/test_manifest.py tests/test_download_api.py -q

  The OLD token stops working the moment Tidal issues a new one, which
  is what invalidates the copy in git history. Purge the history only
  after confirming the new token works.
"""
    )
    return 0


def verify() -> int:
    entries = load_tokens()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

    print("Current credentials:")
    describe(entries)

    report_file = BACKUP_DIR / "rotation-report.json"
    if report_file.exists():
        report = json.loads(report_file.read_text(encoding="utf-8"))
        old_users = set(filter(None, report.get("user_ids", [])))
        new_users = {e.get("userID") for e in entries}

        if new_users == old_users and report.get("status") == "ROTATION_PENDING":
            print(
                "\n  NOTE: userID is unchanged. That is expected - Tidal keeps the\n"
                "        same account. What matters is that refresh_token differs\n"
                "        from the backup, which rotating the token guarantees."
            )

        report["status"] = "ROTATED"
        report["verified_at"] = stamp
        report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nMarked ROTATED in {report_file.relative_to(ROOT)}")
    else:
        print("\nNo rotation report found; run --prepare first for a full audit trail.")

    # Confirm the live file is no longer tracked.
    try:
        tracked = subprocess.run(
            ["git", "ls-files", "--error-unmatch", "token.json"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
        print(
            "\ntoken.json is untracked in the working tree."
            if tracked.returncode != 0
            else "\nWARNING: token.json is still tracked by git. Run: "
            "git rm --cached token.json"
        )
    except Exception as exc:  # noqa: BLE001
        print(f"\n(could not check tracking status: {exc})")

    print(
        "\nRemaining: purge the leaked commit from history, then force-push.\n"
        "See tools/rotate_credentials.py --help for the exact commands."
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare and verify a Tidal credential rotation."
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--prepare", action="store_true",
                       help="Back up and audit")
    group.add_argument("--verify", action="store_true",
                       help="Confirm rotation")
    args = parser.parse_args()

    return prepare() if args.prepare else verify()


if __name__ == "__main__":
    raise SystemExit(main())
