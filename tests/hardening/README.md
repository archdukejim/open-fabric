# tests/hardening

| File | What |
|---|---|
| `run.sh` | Start bind9, step-ca, postgres, keycloak and openbao from their real rendered compose files and check each works (DNS answers, TLS, static seal) and is hardened (non-root, no capabilities, zero effective capabilities, no-new-privileges, read-only root, a memory limit) |
