# Runbook: Rotate the sheets-to-xero service-account key (S3.3)

**Severity:** high — a live RSA private key sits in plaintext at
`config/.credentials.json` inside the repo tree.

**Who runs this:** Molham only. This involves a live Google Cloud secret;
the agent must not touch it.

## 1. Rotate the key in Google Cloud (revokes the leaked one)

1. Identify the service account from `config/.credentials.json` `client_email`
   (the sheets-to-xero SA).
2. In Google Cloud Console → IAM & Admin → Service Accounts → that SA → Keys:
   - Create a new JSON key (downloads a fresh key file).
   - Delete the existing key whose `private_key_id` matches the one in
     `config/.credentials.json`. This revokes the exposed key.

## 2. Move the new key out of the repo tree

```bash
mkdir -p ~/.config/moh_time_os
mv ~/Downloads/<new-sa-key>.json ~/.config/moh_time_os/.credentials.json
chmod 600 ~/.config/moh_time_os/.credentials.json
```

## 3. Point the code at the out-of-repo path

Set the env var (in the daemon/API LaunchAgent plists and your shell profile):

```bash
export CREDENTIALS_JSON_FILE="$HOME/.config/moh_time_os/.credentials.json"
```

`lib/credential_paths.py:credentials_json()` now honors `CREDENTIALS_JSON_FILE`
(S3.3 code change). Verify:

```bash
cd /Users/molhamhomsi/clawd/moh_time_os
CREDENTIALS_JSON_FILE="$HOME/.config/moh_time_os/.credentials.json" \
  .venv/bin/python -c "from lib import credential_paths; p=credential_paths.credentials_json(); print(p, p.exists())"
```

Expected: prints the out-of-repo path and `True`.

## 4. Delete the in-repo plaintext key

```bash
rm /Users/molhamhomsi/clawd/moh_time_os/config/.credentials.json
```

(It is gitignored and untracked — confirmed via `git check-ignore` /
`git ls-files` — so no git history scrub is needed.)

## 5. Confirm collectors still authenticate

This unblocks WS4.S4.1 (restore Xero/Asana credentials + live sync). After the
env var is set, run a manual Xero sync per WS4.S4.1 and confirm `sync_state`
for xero updates.
