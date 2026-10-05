# tests/keycloak

| File | What |
|---|---|
| `run.py` | `keycloak_bootstrap.py` against a real Keycloak and a real Samba AD DC (fabric's image, converged by fabric), twice (idempotent); the admin API's view (AD federation over verified LDAPS, groups, the web UI client, the MFA flow); a browser sign-in by the first admin with fabric's one-time password, forced through TOTP enrolment and a new password that lands in AD; refusals: a disabled person, a person outside the site's groups (D90), an unregistered redirect URI |
