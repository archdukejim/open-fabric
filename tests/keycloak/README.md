# tests/keycloak

| File | What |
|---|---|
| `run.sh` | `keycloak_bootstrap.py` against a real Keycloak and the dirsrv suite's directory, twice (idempotent); a browser sign-in as the directory user is forced into TOTP enrolment; an unregistered redirect URI is refused |
| `verify.py` | Check the Keycloak state the bootstrap produced, through the admin API: brute-force protection, the LDAPS user federation, the web UI client (confidential, PKCE, exact redirect, scoped roles), role bundles, the MFA flow |
