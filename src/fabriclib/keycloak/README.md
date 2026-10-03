# fabriclib/keycloak

Keycloak operations over the admin REST API (TLS pinned to the fabric root
CA, admin credentials from fabric's secrets via `load_secrets`: the secrets
file, or OpenBao once imported). Realm, federation and client setup is still
in `src/ux/cli/keycloak_bootstrap.py` (to be split here), whose `Admin`
client these files use.

| File | What |
|---|---|
| `keycloak_admin.py` | Admin REST client (CA-pinned) and realm name |
| `ensure_rbac_roles.py` | A realm role per fabric permission and a composite role per bundle, converged |
| `ensure_adguard_client.py` | The OIDC client `fabric-adguard` oauth2-proxy signs people into AdGuard's UI with (realm roles in a `roles` claim) |
| `ensure_openbao_client.py` | The `fabric-openbao` OIDC client for OpenBao's own UI (TOTP flow, fabric roles in a `roles` ID-token claim, exact callback) |
| `fabric_groups.py` | The directory groups that carry a fabric bundle |
| `create_person.py` | Helpdesk: a new realm user in `users`, one-time password (changed at first sign-in) |
| `reset_sign_in.py` | Helpdesk: new one-time password, TOTP removed, sessions ended (fabric-group members: admins only) |
| `require_password_change.py` | Import an LDAP user into Keycloak and require a new password at their next login |
| `user_has_role.py` | Whether Keycloak grants a user a realm role (directly or through a group) |
| `verify_user_token.py` | fabric-agent: verify a signed-in person's ID token itself (signature, issuer, audience, expiry) |
| `configure_keycloak.py` | Configure Keycloak idempotently (what `lib/keycloak_bootstrap.py` runs): realm, LDAP, roles, TOTP flow, clients |
| `admin_client.py` | `Admin`: the admin REST client (logs in as the master-realm admin, TLS pinned to the fabric root CA) |
| `quote.py` | `q`: URL-quote one path or query component |
| `step.py` | One progress line of the configuration |
| `ensure_realm.py` | The realm with its login protections (brute-force lockout, no e-mail login) |
| `ensure_ldap_federation.py` | LDAP user federation to 389-DS (created, or updated in place) |
| `ensure_group_mapper.py` | The LDAP group mapper, and a sync of the directory's groups |
| `grant_role_to_group.py` | Give a group a realm role if it does not have it |
| `ensure_mfa_flow.py` | The browser flow with TOTP required for everyone |
| `ensure_webui_client.py` | The web UI's OIDC client (PKCE, exact redirect, TOTP flow, roles claim) |
