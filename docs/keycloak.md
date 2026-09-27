# Keycloak Deployment Documentation

This document tracks connections, variables, configuration nuances, and gotchas for the Keycloak ↔ LDAP (389 Directory Server) integration. The core-web management UI that authenticates through this realm is covered in [coreweb.md](coreweb.md).

## Phase 1: Infrastructure and Bootstrapping

### Configuration Variables
*   **Keycloak Installation**: Enabled via `install_keycloak: true` in `custom-vars.yaml`.
*   **Host IP**: Ensure `host_ip` is correctly set in `custom-vars.yaml`. Mismatched IPs will cause Nginx (and other containers) to fail when binding ports.

### Secrets and Credentials
*   **Locating Passwords**: All generated credentials are safely stored on the target machine in `/opt/core/config/core-secrets.yml`. You can view them by running `cat /opt/core/config/core-secrets.yml`.
*   **LDAP Service Account**: Keycloak uses a dedicated, isolated service account password (`ldap_keycloak_password`) generated automatically by the installer. Every other LDAP role account also has its own generated password (`ldap_super_admin_password`, `ldap_group_admin_password`, `ldap_user_creator_password`, `ldap_user_modifier_password`); there is no shared default password.
*   **core-web Client Secret**: `coreweb_oidc_secret` is the client secret of the `core-mgr` OIDC client.
*   **Keycloak Admin**: The admin credentials (`keycloak_admin_user`, `keycloak_admin_password`) and the PostgreSQL database password (`keycloak_db_password`) are also generated automatically by the installer.

### Identity Preconditioning & Gotchas
*   **Container UIDs vs Host UIDs**: 
    *   By default, Keycloak and PostgreSQL use UIDs `1000` and `999` respectively. However, we have upgraded to Keycloak 26 and PostgreSQL 18 and enforce custom UIDs: `900` for Keycloak and `901` for PostgreSQL.
    *   **Gotcha (Keycloak)**: Keycloak 26 requires write access to `/opt/keycloak/lib/quarkus` to compile its optimized bytecode during startup. If you run it as `user: "900:900"`, it will crash with an `AccessDeniedException` because user `900` cannot write to the container's root-owned library directories.
    *   **Solution**: Run Keycloak with `user: "900:0"`. By running with GID `0` (the root group), Keycloak gains group-write permissions to the internal directories while still maintaining UID `900` isolation on the host.
    *   **Gotcha (PostgreSQL)**: PostgreSQL 16+ introduces strict mount point boundaries. If you map `/opt/postgres/data` directly to `/var/lib/postgresql/data`, PostgreSQL will refuse to initialize, citing that the directory is an `(unused mount/volume)`.
    *   **Solution**: Set the `PGDATA` environment variable to a subdirectory, e.g., `/var/lib/postgresql/data/pgdata`. PostgreSQL will successfully create and manage this subdirectory.
*   **kcadm.sh Configuration** (manual use only — the installer no longer calls `kcadm.sh`, see Phase 3):
    *   **Gotcha**: When Keycloak runs as a non-root user (e.g. UID 900), its home directory evaluates to `/`, which it cannot write to. Running `kcadm.sh` commands will fail with `Failed to create config file: /.keycloak/kcadm.config`.
    *   **Solution**: Append `--config /tmp/kcadm.config` immediately after the `kcadm.sh` command (e.g., `kcadm.sh config credentials --config /tmp/kcadm.config ...`) to write the configuration to a writable temporary directory.
*   **Healthchecks and Systemd**: 
    *   Keycloak 24+ running on Quarkus does not enable health endpoints by default.
    *   **Gotcha**: If `KC_HEALTH_ENABLED: "true"` is not explicitly set in the Keycloak environment variables, the systemd `ExecStartPost` health check will fail (timing out after 60 seconds), causing dependent services like `nginx` to fail to start. Also, Keycloak 26 removed `curl` from its base image, causing Docker healthchecks relying on `curl` to fail.
    *   **Solution**: The docker-compose `test` command must rely on bash TCP streams (e.g., `exec 3<>/dev/tcp/127.0.0.1/9000`) instead of `curl` to query `/health/ready`.

---
*End of Phase 1 Notes*

## Phase 3: LDAP Federation Configuration

### Automated Configuration (`keycloak_bootstrap.py`)
Playbook 09 runs `core/lib/keycloak_bootstrap.py`, which talks to the Keycloak admin REST API over TLS pinned to the core root CA. Credentials are read from `core-secrets.yml` — nothing is passed on a command line. It is idempotent (converges on every run) and can be re-run at any time:

```bash
sudo core-mgr --keycloak-sync
```

| Object | Configuration |
|--------|---------------|
| Realm | `coreweb_realm` (default: `domain`); brute-force protection on (5 failures, temporary lockout) |
| User federation | LDAP provider `389-DS`: vendor `rhds`, `ldaps://<hostname_ldap>:3636`, UUID attribute `entryUUID`, username/RDN `uid`, edit mode `WRITABLE`, sync registrations on. An existing provider named `OpenLDAP` is **updated in place** so federated user links survive the migration. |
| Group mapper | `LDAP Groups` (`group-ldap-mapper`) on `ou=groups,<base_dn>`, synced into Keycloak |
| Realm role | `coreweb_admin_role` (default `core-admin`), granted to group `coreweb_admin_group` (default `admins`) |
| OIDC client | `core-mgr` — confidential, code flow + PKCE `S256`, exact redirect `https://<hostname_mgr>/oidc/callback`, `fullScopeAllowed: false`, realm roles in the ID token `roles` claim |
| Auth flow | `core-mgr-browser-mfa` — browser flow with TOTP **REQUIRED**, bound to the `core-mgr` client only (other clients keep the realm default flow) |

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
*   Keycloak is bound to 389-DS using the dedicated `cn=keycloak_admin,ou=admins,ou=accounts,{{ ldap_base_dn }}` service account, utilizing the isolated `ldap_keycloak_password`.
*   Users are searched in `ou=users,ou=accounts,{{ ldap_base_dn }}`.
*   Groups are searched in `ou=groups,{{ ldap_base_dn }}`.
*   **Gotcha**: Keycloak connects to the `dirsrv` container directly on `core_net` (not through nginx), so the URL must use the container-side port **3636** and the exact LDAP hostname: `ldaps://{{ hostname_ldap }}:3636`. The bare `ldap` name fails resolution (`UnknownHostException`) — only `hostname_ldap` is a Docker alias — and the hostname must match the certificate SAN.
*   **UUID attribute**: `entryUUID` (provided by the 389-DS `entryuuid` plugin, enabled by the seed). Keycloak links federated users by this value, which is why the OpenLDAP migration preserves it.

---
*End of Phase 3 Notes*

## Phase 4: Security & ACLs

### 389-DS Seeding (cn=config and the tree)
*   The seed LDIFs in `/opt/dirsrv/seed/` are applied by `seed.py` **inside** the container over LDAPI as Directory Manager (`dirsrv.sh seed`, run by playbook 09 and by `core-mgr --apply` when a seed file changes). Entries are only added when missing; `changetype: modify` records only touch differing values; if anything under `cn=config` changed, the `ldap` service is restarted once.
*   `00-config.ldif` hardens the server: `nsslapd-require-secure-binds: on`, `nsslapd-minssf: 56` (rootDSE excluded), TLS 1.2 minimum, `PBKDF2-SHA512` password storage, password syntax checks (min length 12, 3 categories), lockout after 5 failures for 900 s, and enables the `memberOf` and `entryUUID` plugins.
*   `10-tree.ldif` creates the suffix, OUs and groups (`groupOfNames` + `posixGroup`, so both `member` and `gidNumber` work). `20-accounts.ldif` creates the role accounts. `30-aci.ldif` holds the ACIs.

### TLS Enforcement and Simple Binds
*   **Gotcha**: 389-DS terminates TLS itself; nginx only passes TCP through (389 → `dirsrv:3389`, 636 → `dirsrv:3636`). On port 389 everything except StartTLS and the rootDSE is refused until the connection is encrypted, so a plain `ldapsearch -x -H ldap://…` bind fails with `Confidentiality required` / `Minimum SSF not met`.
*   **Solution**: Use `-ZZ` (StartTLS) on 389 or `ldaps://` on 636, with the core root CA trusted (`LDAPTLS_CACERT=/opt/stepca/data/certs/root_ca.crt`). Inside the container, LDAPI (`ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket`) counts as a secure channel.

```bash
LDAPTLS_CACERT=/opt/stepca/data/certs/root_ca.crt \
  ldapwhoami -H ldaps://ldap.<domain> -x -D "cn=super_admin,ou=admins,ou=accounts,<base_dn>" -W
```

### Access Control (ACIs)
*   **Anonymous**: may read/search only POSIX name-service attributes (`uid`, `uidNumber`, `gidNumber`, `memberUid`, `member`, `memberOf`, `homeDirectory`, `loginShell`, …) — enough for sssd — and only over TLS (minssf). Never `userPassword`.
*   **Authenticated users**: read everything except `userPassword` and `aci`; may change their own password.
*   **`super_admin`**: full control. **`group_admin`**: manages `ou=groups`. **`user_creator_admin`** / **`user_modifier_admin`**: add / edit entries in `ou=users,ou=accounts`. Group `owner`s may edit membership.
*   **`keycloak_admin`**: add, edit and delete users in `ou=users` and manage `ou=groups` — nothing else, so it cannot modify role accounts like `cn=super_admin`.

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
