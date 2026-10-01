# Keycloak Deployment Documentation

This document tracks connections, variables, configuration nuances, and gotchas for the Keycloak ↔ LDAP (389 Directory Server) integration. The web UI (Open Fabric) that authenticates through this realm, and the permissions and bundles it checks, are covered in [webui.md](webui.md); OpenBao's own UI signs in through the same realm.

## Phase 1: Infrastructure and Bootstrapping

### Configuration Variables
*   **Keycloak Installation**: Enabled via `install_keycloak: true` in `custom-vars.yaml`.
*   **Host IP**: Ensure `host_ip` is correctly set in `custom-vars.yaml`. Mismatched IPs will cause Nginx (and other containers) to fail when binding ports.

### Secrets and Credentials
*   **Locating Passwords**: All generated credentials are fabric's secrets, kept in OpenBao (`fabric/secrets`) once setup has finished. List them with `sudo fabricctl secrets list` and print one with `sudo fabricctl secrets show keycloak_admin_password` (every read is audited).
*   **LDAP Service Account**: Keycloak uses a dedicated, isolated service account password (`ldap_keycloak_password`) generated automatically by the installer. Every other LDAP role account also has its own generated password (`ldap_super_admin_password`, `ldap_group_admin_password`, `ldap_user_creator_password`, `ldap_user_modifier_password`, `ldap_device_admin_password`, `ldap_radius_password`); there is no shared default password.
*   **OIDC Client Secrets**: `webui_oidc_secret` is the client secret of the `fabric-webui` OIDC client (the web UI); `openbao_oidc_secret` that of `fabric-openbao` (OpenBao's own UI). Both are generated.
*   **Keycloak Admin**: The master-realm admin is `keycloak_admin_user` (default `admin`) with the generated `keycloak_admin_password`; the PostgreSQL database password (`keycloak_db_password`) is generated too. They reach the container as Keycloak's bootstrap-admin environment (`KC_BOOTSTRAP_ADMIN_USERNAME` / `_PASSWORD`).

### Identity Preconditioning & Gotchas
*   **Container UIDs vs Host UIDs**: 
    *   By default, Keycloak and PostgreSQL use UIDs `1000` and `999` respectively. However, we have upgraded to Keycloak 26 and PostgreSQL 18 and enforce custom UIDs (`service_users`): `900` for Keycloak and `901` for PostgreSQL.
    *   **Gotcha (Keycloak)**: A stock Keycloak 26 image compiles its optimized bytecode at every start and needs write access to `/opt/keycloak/lib/quarkus` for it. Run as `user: "900:900"`, it crashes with an `AccessDeniedException` because user `900` cannot write to the container's root-owned library directories.
    *   **Solution**: fabric builds its own pre-built image (`fabric/keycloak:local` from `fabricctl/jinja/keycloak/build/Dockerfile`, on the pinned `image_keycloak`): `kc.sh build` runs once at image build time and the container starts with `start --optimized`, so nothing is written at start and the root filesystem is read-only. Keycloak still runs as `user: "900:0"` (the default `service_users.keycloak`; group `0` owns Keycloak's files in the image).
    *   **Gotcha (PostgreSQL)**: PostgreSQL 16+ introduces strict mount point boundaries. If you map `/opt/postgres/data` directly to `/var/lib/postgresql/data`, PostgreSQL will refuse to initialize, citing that the directory is an `(unused mount/volume)`.
    *   **Solution**: Set the `PGDATA` environment variable to a subdirectory, e.g., `/var/lib/postgresql/data/pgdata`. PostgreSQL will successfully create and manage this subdirectory.
*   **kcadm.sh Configuration** (manual use only — the installer no longer calls `kcadm.sh`, see Phase 3):
    *   **Gotcha**: When Keycloak runs as a non-root user (e.g. UID 900), its home directory evaluates to `/`, which it cannot write to. Running `kcadm.sh` commands will fail with `Failed to create config file: /.keycloak/kcadm.config`.
    *   **Solution**: Append `--config /tmp/kcadm.config` immediately after the `kcadm.sh` command (e.g., `kcadm.sh config credentials --config /tmp/kcadm.config ...`) to write the configuration to a writable temporary directory.
*   **Healthchecks and Systemd**: 
    *   Keycloak 24+ running on Quarkus does not enable health endpoints by default.
    *   **Gotcha**: Without `KC_HEALTH_ENABLED=true` the management port (9000) and its health endpoints do not exist, so the Docker health check never passes and the systemd `ExecStartPost` wait fails, causing dependent services like `nginx` to fail to start. Also, Keycloak 26 removed `curl` from its base image, causing Docker healthchecks relying on `curl` to fail.
    *   **Solution**: `KC_HEALTH_ENABLED=true` is a build-time option, set in the pre-built image's Dockerfile. The docker-compose `test` uses a bash TCP stream instead of `curl`: `exec 3<>/dev/tcp/127.0.0.1/9000` succeeds once the management port accepts connections (it does not read `/health/ready`).

---
*End of Phase 1 Notes*

## Phase 3: LDAP Federation Configuration

### Automated Configuration (`keycloak_bootstrap.py`)
The `start` setup step (and `fabricctl --keycloak-sync`) runs `fabricctl/lib/keycloak_bootstrap.py`, which talks to the Keycloak admin REST API at `ip_keycloak:8443` over TLS pinned to the core root CA, as the master-realm admin. Credentials are read from fabric's secrets (the secrets file during the first setup, OpenBao once imported) — nothing is passed on a command line. It is idempotent (converges on every run) and can be re-run at any time:

```bash
sudo fabricctl --keycloak-sync
```

| Object | Configuration |
|--------|---------------|
| Realm | `webui_realm` (default: `domain`), created if missing; brute-force protection on (5 failures, temporary lockout growing by 1 min up to 15 min, never permanent); sign-in by e-mail off, duplicate e-mails refused |
| User federation | LDAP provider `389-DS` (only with `install_ldap`): vendor `rhds`, `ldaps://<hostname_ldap>:3636`, bound as `cn=keycloak_admin`, users one level under `ou=users,ou=accounts,<base_dn>`, UUID attribute `entryUUID`, username/RDN `uid`, edit mode `WRITABLE` (password changes use the LDAP password-modify operation), import and sync registrations on (users created in Keycloak are written to 389-DS). An existing LDAP provider is updated in place: fabric's settings win, others are kept. |
| Group mapper | `LDAP Groups` (`group-ldap-mapper`) on `ou=groups,<base_dn>` (`groupOfNames`, `member`), mode `LDAP_ONLY` (memberships live in 389-DS), synced into Keycloak on every run |
| Realm roles | fabric's access control (`fabriclib/keycloak/ensure_rbac_roles.py`): one role per permission, `fabric:<area>:<action>`, and one composite role per bundle holding exactly its permissions (extra `fabric:` members are removed). The admin bundle is `webui_admin_role` (default `fabric-admin`), granted to group `webui_admin_group` (default `admins`); every other bundle is granted to the `ldap_groups` entries that name it (`auditors`, `network-operators`, …). The list of permissions and bundles is in [webui.md](webui.md#who-may-do-what) |
| OIDC client | `fabric-webui` (only with `install_webui`) — confidential, code flow + PKCE `S256` only (no implicit or direct grants), exact redirect `https://<hostname_mgr>/oidc/callback`, logout back to `https://<hostname_mgr>/`, `fullScopeAllowed: false` with every fabric role in its scope, realm roles in the ID token `roles` claim |
| OIDC client | `fabric-openbao` (when `openbao_oidc_secret` exists, i.e. once OpenBao is set up) — OpenBao's own UI: confidential, code flow, exact redirect `https://<hostname_openbao>/ui/vault/auth/oidc/oidc/callback`, the same role scope and `roles` claim (`fabriclib/keycloak/ensure_openbao_client.py`) |
| Auth flow | `fabric-webui-mfa` — a copy of the browser flow with TOTP **REQUIRED** (users without TOTP must enrol), bound to the `fabric-webui` and `fabric-openbao` clients only (other clients keep the realm default flow) |

The web UI's **People** page (`fabriclib/keycloak/create_person.py`, `reset_sign_in.py`) also uses this admin API through fabric-agent: *Add a person* creates a realm user in the plain `users` group with a temporary one-time password; *Reset sign-in* sets a new one, deletes the user's TOTP credential and ends their sessions (members of fabric groups: admins only). Setup's first admin gets `UPDATE_PASSWORD` as a required action (`require_password_change.py`), and `fabricctl doctor` checks that Keycloak grants that admin `webui_admin_role` (`user_has_role.py`).

### Manual kcadm.sh Notes
These still apply if you drive `kcadm.sh` by hand inside the container.
*   **kcadm.sh Connection**: When running `kcadm.sh config credentials` inside the Keycloak container, using `--server https://localhost:8443` will fail with a `SunCertPathBuilderException` because the internal Java truststore does not automatically trust the generated certificates without explicit Java keystore configuration. 
    *   **Gotcha**: Using `--insecure` does not bypass this specific PKIX path building failure in Keycloak 24.
    *   **Solution**: Connect to the local HTTP port instead: `--server http://localhost:8080`.
*   **Property Naming in Keycloak 24**:
    *   **Gotcha**: When configuring the `group-ldap-mapper` via `kcadm.sh`, older camelCase property names (e.g., `groupsDn`, `groupNameLDAPAttribute`) will fail with errors like `Missing configuration for LDAP Groups DN`.
    *   **Solution**: Keycloak 24 expects dot-separated property names (e.g., `groups.dn`, `group.name.ldap.attribute`).
    *   **Gotcha 2**: When using `kcadm.sh` with the `-s` flag, properties with dots are parsed as nested JSON objects unless the keys are explicitly quoted.
    *   **Solution**: You must quote the keys: `-s 'config."groups.dn"=["ou=groups,{{ ldap_base_dn }}"]'`.

### LDAP Service Account Bind
*   Keycloak is bound to 389-DS using the dedicated `cn=keycloak_admin,ou=admins,{{ ldap_local_dn }}` (the install's local suffix) service account, utilizing the isolated `ldap_keycloak_password`.
*   Users are searched in `ou=users,ou=accounts,{{ ldap_base_dn }}`.
*   Groups are searched in `ou=groups,{{ ldap_base_dn }}`.
*   **Gotcha**: Keycloak connects to the `dirsrv` container directly on `fabric_net` (not through nginx), so the URL must use the container-side port **3636** and the exact LDAP hostname: `ldaps://{{ hostname_ldap }}:3636`. The bare `ldap` name fails resolution (`UnknownHostException`) — only `hostname_ldap` is a Docker alias — and the hostname must match the certificate SAN.
*   **UUID attribute**: `entryUUID` (provided by the 389-DS `entryuuid` plugin, enabled by the seed). Keycloak links federated users by this value.

---
*End of Phase 3 Notes*

## Phase 4: Security & ACLs

### 389-DS Seeding (cn=config and the tree)
*   The seed LDIFs in `/opt/dirsrv/seed/` are applied by `seed.py` **inside** the container over LDAPI as Directory Manager (`dirsrv.sh seed`, run by the `start` setup step and by `fabricctl --apply` when a seed file changes). Entries are only added when missing; `changetype: modify` records only touch differing values; if anything under `cn=config` changed, the `ldap` service is restarted once.
*   `00-config.ldif` hardens the server: `nsslapd-require-secure-binds: on`, `nsslapd-minssf: 56` (rootDSE excluded), TLS 1.2 minimum, `PBKDF2-SHA512` password storage, password syntax checks (min length 12, 3 categories), lockout after 5 failures for 900 s, and enables the `memberOf` and `entryUUID` plugins.
*   `10-tree.ldif` creates the suffix, OUs and groups (`groupOfNames` + `posixGroup`, so both `member` and `gidNumber` work). `20-accounts.ldif` creates the role accounts. `30-aci.ldif` holds the ACIs.

### TLS Enforcement and Simple Binds
*   **Gotcha**: 389-DS terminates TLS itself; nginx only passes TCP through (389 → `dirsrv:3389`, 636 → `dirsrv:3636`). On port 389 everything except StartTLS and the rootDSE is refused until the connection is encrypted, so a plain `ldapsearch -x -H ldap://…` bind fails with `Confidentiality required` / `Minimum SSF not met`.
*   **Solution**: Use `-ZZ` (StartTLS) on 389 or `ldaps://` on 636, with the core root CA trusted (`LDAPTLS_CACERT=/opt/stepca/data/certs/root_ca.crt`). Inside the container, LDAPI (`ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket`) counts as a secure channel.

```bash
LDAPTLS_CACERT=/opt/stepca/data/certs/root_ca.crt \
  ldapwhoami -H ldaps://ldap.<domain> -x -D "cn=super_admin,ou=admins,ou=<site_name>,<base_dn>" -W
```

### Access Control (ACIs)
*   **Anonymous**: may read/search only POSIX name-service attributes (`uid`, `uidNumber`, `gidNumber`, `memberUid`, `member`, `memberOf`, `homeDirectory`, `loginShell`, …) — enough for sssd — and only over TLS (minssf). Never `userPassword`.
*   **Authenticated users**: read everything except `userPassword` and `aci`; may change their own password.
*   **`super_admin`**: full control. **`group_admin`**: manages `ou=groups`. **`user_creator_admin`** / **`user_modifier_admin`**: add / edit entries in `ou=users,ou=accounts`. Group `owner`s may edit membership.
*   **`keycloak_admin`**: add, edit and delete users in `ou=users` and manage `ou=groups` — nothing else, so it cannot modify role accounts like `cn=super_admin`.
*   **`device_admin`** (fabric-agent, for the web UI's devices and roles): manages `ou=devices` and `ou=device-roles` only. **`radius_reader`** (FreeRADIUS) only reads: the devices of this install's local suffix and, like any authenticated account, the organisation.

---
*End of Phase 4 Notes*

## Phase 5: Identity Brokering & Federation

### Linking Federated Identities to LDAP Users
When configuring Keycloak to trust an external Identity Provider (IdP) (e.g., another Keycloak instance, Google, or Microsoft Entra ID), you may want to map users authenticating via the external IdP to your existing local LDAP user accounts.

If the usernames across the systems differ, there are three primary ways to link these identities:

1. **Automatic Linking via Email (First Broker Login Flow):**
   If the external Identity Provider provides an email address claim that exactly matches the `mail` attribute of the existing LDAP user in Keycloak, the default "First Broker Login" authentication flow will detect the conflict. It will automatically prompt the user to link their account by either verifying their email address or entering their local LDAP password. Once verified, the external identity is permanently linked to the local LDAP account.

2. **Manual Linking via Admin Console:**
   If the usernames and emails are completely different, a Keycloak administrator can manually establish the link between the external identity and the LDAP user:
   * Log into the Keycloak Admin Console.
   * Navigate to **Users** and search for the target LDAP user.
   * Click on the user to open their details, then navigate to the **Identity Provider Links** tab.
   * Click **Link account**.
   * Select the configured Identity Provider from the dropdown.
   * Enter the user's exact **Identity Provider Username** (the username they use on the external system) and click **Save**.

3. **User-Initiated Linking (Account Console):**
   If a user is already capable of logging in with their local LDAP credentials, they can link their own federated identity manually:
   * The user logs into the Keycloak Account Console (`/realms/{realm-name}/account/`).
   * Navigate to the **Linked Accounts** section.
   * Click the link/connect button next to the desired external Identity Provider and authenticate on that external system to bind the identity.

---
*End of Phase 5 Notes*

## Phase 6: Smart Cards & Security Keys

Keycloak handles smart cards differently depending on whether you are using a modern FIDO2 Security Key or a traditional X.509 Client Certificate.

### 1. Modern Security Keys / FIDO2 (e.g., YubiKeys)
Keycloak provides a built-in, self-service registration portal for modern security keys (WebAuthn). Users can register their own hardware tokens without administrator intervention.

*   **Registration Tool:** The Keycloak Account Console.
*   **Process:** 
    1. The user logs in with their standard LDAP credentials (or federated identity).
    2. They navigate to their Account Console (`https://<sso-domain>/realms/{realm-name}/account/`).
    3. Under **Account Security > Signing In**, they locate the **Security Key (WebAuthn)** or **Passwordless** section.
    4. They click "Set up", insert their hardware token, and follow their browser's prompt to complete the physical registration to their specific user account.

### 2. Traditional Smart Cards (X.509 Client Certificates like CAC/PIV)
There is **no built-in, user-facing "registration tool"** for traditional X.509 smart cards in Keycloak. Instead of "registering" a card, the authentication identity is mapped based on the data baked into the certificate on the card itself.

When configuring Keycloak's **X.509/Validate Username Authenticator**, the mapping usually happens in one of two ways:
*   **Automatic LDAP/Active Directory Mapping:** If the certificate on the smart card contains an email address or User Principal Name (UPN) that exactly matches a user already in your LDAP directory, Keycloak will automatically authenticate them into that account. No "registration" is required.
*   **Manual Administrative Mapping:** If the certificates do not map to your LDAP attributes cleanly, an administrator must manually edit the user in the Keycloak Admin Console and paste a unique identifier from the user's certificate (like the Subject DN) into a custom attribute field so Keycloak knows who the card belongs to.

*(Note: If you strictly require a self-service registration portal where a user logs in with a password, inserts their smart card, and the system permanently links that specific card's certificate to their account, you would have to write a custom Java extension (SPI) for Keycloak, as it does not natively support self-service X.509 enrollment.)*
