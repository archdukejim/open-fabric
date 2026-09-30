# fabriclib/keycloak

Keycloak operations over the admin REST API (TLS pinned to the fabric root
CA, admin credentials from fabric's secrets via `load_secrets`: the secrets
file, or OpenBao once imported). Realm, federation and client setup is still
in `fabricctl/lib/keycloak_bootstrap.py` (to be split here), whose `Admin`
client these files use.

| File | What |
|---|---|
| `keycloak_admin.py` | Admin REST client (CA-pinned) and realm name |
| `ensure_rbac_roles.py` | A realm role per fabric permission and a composite role per bundle, converged |
| `ensure_openbao_client.py` | The `fabric-openbao` OIDC client for OpenBao's own UI (TOTP flow, fabric roles in a `roles` ID-token claim, exact callback) |
| `fabric_groups.py` | The directory groups that carry a fabric bundle |
| `create_person.py` | Helpdesk: a new realm user in `users`, one-time password (changed at first sign-in) |
| `reset_sign_in.py` | Helpdesk: new one-time password, TOTP removed, sessions ended (fabric-group members: admins only) |
| `require_password_change.py` | Import an LDAP user into Keycloak and require a new password at their next login |
| `user_has_role.py` | Whether Keycloak grants a user a realm role (directly or through a group) |
| `verify_user_token.py` | fabric-agent: verify a signed-in person's ID token itself (signature, issuer, audience, expiry) |
