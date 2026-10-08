# scripts/release

Release chores the repository's owner runs by hand (manual 4.7.1).

| File | What |
|---|---|
| `make-apt-key.sh` | Make the apt repository's signing key once and store it in the Actions secrets, with an offline copy (the key, its passphrase, the revocation certificate) in a folder you keep offline |
