# tests/keycloak

| File | What |
|---|---|
| `run.sh` | `keycloak_bootstrap.py` against a real Keycloak and the dirsrv suite's directory, twice (idempotent) |
| `verify.py` | Check the Keycloak state the bootstrap produced, through the admin API |
