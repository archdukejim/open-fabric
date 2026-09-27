# fabriclib/keycloak

Keycloak operations over the admin REST API (TLS pinned to the fabric root
CA, credentials from `fabric-secrets.yml`). Realm, federation and client
setup is still in `fabric/lib/keycloak_bootstrap.py` (to be split here).

| File | What |
|---|---|
| `require_password_change.py` | Import an LDAP user into Keycloak and require a new password at their next login |
| `user_has_role.py` | Whether Keycloak grants a user a realm role (directly or through a group) |
