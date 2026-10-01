"""Prune token.json down to a single, non-compromised credential.

tidal_auth.py appends rather than replaces, so a rotation leaves the old
(leaked) credential in place. This keeps only the newest entry per userID and
drops any userID listed as compromised.

Run with:
    python tools/prune_credentials.py --keep 209418833
    python tools/prune_credentials.py --keep-newest
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOKEN_FILE = ROOT / "token.json"
BACKUP_DIR = ROOT / ".credential-backup"

# userID that was committed to GitHub at 5589382.
LEAKED_USER_IDS = {"209282720"}


def load() -> list[dict]:
    if not TOKEN_FILE.exists():
        sys.exit("token.json not found.")
    data = json.loads(TOKEN_FILE.read_text(encoding="utf-8"))
    return [data] if isinstance(data, dict) else data


def backup(entries: list[dict], tag: str) -> Path:
    BACKUP_DIR.mkdir(exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = BACKUP_DIR / f"token.{stamp}.{tag}.json.bak"
    path.write_text(json.dumps(entries, indent=2), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--keep", help="userID to retain")
    group.add_argument(
        "--keep-newest",
        action="store_true",
        help="retain the most recently added entry",
    )
    args = parser.parse_args()

    entries = load()
    print(f"Before: {len(entries)} credential(s)")
    for e in entries:
        print(f"  userID={e.get('userID')} role={e.get('role') or 'playback'}")

    # Choose which single credential to keep.
    if args.keep:
        chosen = [e for e in entries if str(e.get("userID")) == str(args.keep)]
        if not chosen:
            sys.exit(f"No credential with userID {args.keep}.")
    else:
        chosen = [entries[-1]]

    kept = chosen[-1]
    kept_id = str(kept.get("userID"))

    if kept_id in LEAKED_USER_IDS:
        sys.exit(
            f"Refusing to keep userID {kept_id}: it is the credential exposed in\n"
            "git history. Re-run tidal_auth.py to authorize a different account, "
            "then prune with --keep <new userID>."
        )

    # Preserve catalog credentials: they are not the leaked playback token, and
    # dropping them would break metadata endpoints.
    survivors = [e for e in entries if str(e.get("userID")) == kept_id]
    for e in entries:
        if e.get("role") == "catalog" and str(e.get("userID")) != kept_id:
            if str(e.get("userID")) not in LEAKED_USER_IDS:
                survivors.append(e)

    dropped = len(entries) - len(survivors)
    saved = backup(entries, "prune-backup")
    TOKEN_FILE.write_text(json.dumps(survivors, indent=2), encoding="utf-8")

    print(f"\nAfter: {len(survivors)} credential(s), dropped {dropped}")
    for e in survivors:
        print(f"  userID={e.get('userID')} role={e.get('role') or 'playback'}")
    print(f"\nBackup: {saved.relative_to(ROOT)}")

    # Record the outcome.
    report_file = BACKUP_DIR / "rotation-report.json"
    if report_file.exists():
        report = json.loads(report_file.read_text(encoding="utf-8"))
        report["status"] = "ROTATED_AND_PRUNED"
        report["retained_user_ids"] = [
            str(e.get("userID")) for e in survivors
        ]
        report["dropped_user_ids"] = sorted(
            {
                str(e.get("userID"))
                for e in entries
                if str(e.get("userID")) not in
                {str(x.get("userID")) for x in survivors}
            }
        )
        report["pruned_at"] = datetime.now(timezone.utc).strftime(
            "%Y%m%dT%H%M%SZ"
        )
        report_file.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Report: {report_file.relative_to(ROOT)}")

    print("\nNext: purge the leaked commit, then force-push.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
