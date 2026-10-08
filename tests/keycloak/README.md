# tests/keycloak

| File | What |
|---|---|
| `run.py` | `keycloak_bootstrap.py` against a real Keycloak and a real Samba AD DC (fabric's image, converged by fabric), twice (idempotent); the admin API's view (AD federation over verified LDAPS, groups, the web UI client, fabric's sign-in flows, Kerberos and passkey settings); a browser sign-in by the first admin with fabric's one-time password (a new password that lands in AD); raising the admin tools to TOTP; Kerberos sign-in from a domain client (and its CNAME name, its fallback, off); passkeys and `any`; refusals: a disabled person, a person outside the site's groups (2.1.6.14), an unregistered redirect URI, a missing or wrong second factor; `fabricctl sso` |
| `soft_passkey.py` | A software passkey (ES256, user verification, attestation none) for Keycloak's WebAuthn forms |
