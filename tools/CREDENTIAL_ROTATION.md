# Credential Rotation

`token.json` was committed at `5589382` and pushed to
`https://github.com/dev-760/hifi-api`, so the refresh token it contained must be
treated as compromised. This document covers rotating it and purging the history.

## Current state

| Step | Status |
| --- | --- |
| New token obtained | done |
| Compromised token removed from `token.json` | done |
| `token.json` untracked going forward | done (`.gitignore`) |
| Leaked commit purged from history | **pending** |
| Force-push to GitHub | **pending** |

Rotating the token is what actually invalidates the leaked copy: the old
refresh token no longer works, so anyone who cloned the repository cannot use
it. Purging history is hygiene on top of that, not the primary defence.

## Why the leaked credential had to be removed manually

`tidal_auth.py` **appends** to `token.json` rather than replacing it, so running
it does not remove the old entry. `tools/prune_credentials.py` exists to close
that gap.

## Rotating

```bash
# 1. Back up and audit what is exposed
python tools/rotate_credentials.py --prepare

# 2. Authorize a new token (opens a Tidian login URL)
pip install -r tidal_auth/requirements.txt
python tidal_auth/tidal_auth.py

# 3. Keep only the new credential
python tools/prune_credentials.py --keep <new_userID>

# 4. Confirm
python tools/rotate_credentials.py --verify
python -m pytest tests/test_manifest.py tests/test_download_api.py -q
```

`prune_credentials.py` refuses to keep a userID listed in `LEAKED_USER_IDS`, so
it cannot be used to accidentally re-introduce the compromised credential.
Catalog credentials (entries with `"role": "catalog"`) are preserved unless they
are the leaked one, so metadata endpoints keep working.

## Purging history

Only do this **after** the new token is confirmed working.

```bash
# Install once
pip install git-filter-repo

# Back up the repo elsewhere first
git clone --mirror https://github.com/dev-760/hifi-api.git ../hifi-api-backup.git

# Remove the file from all history
git filter-repo --path token.json --invert-paths

# Force-push
git push --force --mirror origin
```

Then have GitHub purge cached views of the old commit:

- <https://github.com/contact/support> — request "remove sensitive data"

Verify:

```bash
git log --all --oneline -- token.json   # should print nothing
```

Anyone who cloned the repository before the purge still has the old token
locally, which is exactly why the rotation has to happen **before** the purge.

## Preventing a repeat

- `token.json` and `*.json.bak` are in `.gitignore`.
- `tools/rotate_credentials.py --prepare` prints the commits that still contain
  the file, so a leak is auditable.
- Consider pre-commit hooks or secret scanning if this repo is shared.

## Note on accounts

Rotating authorized a **different** Tidal account than the one in the leaked
file (userID `209418833` vs `209282720`). Tidal also reported:

```
401 / subStatus 5003
"Requested quality is not allowed in user's subscription"
```

The new account may not have a HI_RES subscription, in which case
`HI_RES_LOSSLESS` downloads will be refused. `LOSSLESS` and below should still
work. If HI_RES is needed, authorize an account with the right tier.
