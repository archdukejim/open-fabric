# fabriclib/keycloak

Keycloak operations over the admin REST API (TLS pinned to the fabric root
CA, credentials from `fabric-secrets.yml`). Realm, federation and client
setup is still in `fabric/lib/keycloak_bootstrap.py` (to be split here).

| File | What |
|---|---|
| `require_password_change.py` | Import an LDAP user into Keycloak and require a new password at their next login |
| `ensure_rbac_roles.py` | A realm role per fabric permission and a composite role per bundle, converged |
| `verify_user_token.py` | fabric-agent: verify a signed-in person's ID token itself (signature, issuer, audience, expiry) |
| `ensure_openbao_client.py` | The `fabric-openbao` OIDC client for OpenBao's own UI (TOTP flow, admin role claim, exact callback) |
| `user_has_role.py` | Whether Keycloak grants a user a realm role (directly or through a group) |
