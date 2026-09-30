# tests/hardening

| File | What |
|---|---|
| `run.sh` | Start bind9, step-ca, postgres, keycloak and dirsrv from their real rendered compose files and check each works and is hardened (non-root, no capabilities, no-new-privileges, read-only root) |
