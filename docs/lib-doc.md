# fabric Library Scripts Documentation

The `fabric/lib/` directory contains modular Bash scripts sourced by the main executables (`setup.sh`, `offline.sh`, etc.), as well as the Python engines (`interactive.py`, `deploy.py`, `keycloak_bootstrap.py`, the `agent/` and `webui/` packages) and legacy bash wrapper (`manage.sh`) that power the `fabricctl` CLI and the webui UI. These scripts provide specific functional domains to keep the entry point scripts clean.

> **Note**: The bash files are designed to be sourced (e.g., `source fabric/lib/output.sh`) and should not be executed directly.

### Table of Contents
- [1. `archive.sh`](#1-archivesh)
- [2. `certs.sh`](#2-certssh)
- [3. `deploy.py`](#3-deploypy)
- [4. `dns.sh`](#4-dnssh)
- [5. `interactive.py`](#5-interactivepy)
- [6. `manage.sh`](#6-managesh)
- [7. `output.sh`](#7-outputsh)
- [8. `package.sh`](#8-packagesh)
- [9. `prereqs.sh`](#9-prereqssh)
- [10. `services.sh`](#10-servicessh)
- [11. `ssh.sh`](#11-sshsh)
- [12. `tsig.sh`](#12-tsigsh)
- [13. `vars.sh`](#13-varssh)
- [14. `dirsrv.sh`](#14-dirsrvsh)
- [15. `ldap_migrate.sh` / `ldap_migrate.py`](#15-ldap_migratesh--ldap_migratepy)
- [16. `keycloak_bootstrap.py`](#16-keycloak_bootstrappy)
- [17. `webui/`](#17-webui)
- [18. `agent/`](#18-agent)

### 1. `archive.sh`
**Purpose**: Backup and snapshot utilities.
- Provides the `archive_snapshot()` function which creates a point-in-time snapshot of the current `/opt/fabric/` installation before applying structural updates or configuration changes. 
- It uses timestamps to keep multiple isolated snapshots in `fabric/archive/`.

### 2. `certs.sh`
**Purpose**: Certificate minting and management workflows.
- Contains the core logic for the `--mint-certs`, `--service-cert` and `--client-cert` operations.
- `do_client_cert()` mints a webui admin certificate (CN = Keycloak username) via `_mint_extra_cert()` and packs it with the chain into a password-protected `~/<user>-fabricctl.p12`, then shreds the loose key.
- Interacts directly with the running `step-ca` container to issue new leaf certificates or subordinate CAs (`_mint_extra_cert()`).
- Bundles intermediate CA logic and formats output correctly for BIND9/NGINX.

### 3. `deploy.py`
**Purpose**: Python-native deployment and state synchronization.
- Directly loads Jinja2 and variable context, rendering templates natively without Ansible overhead.
- Compares generated configurations against live states, performing surgical restarts (via `systemctl`) or safe reloads (via `rndc` or `nginx -s reload`) to apply structural changes (like `host_ram_capacity`).
- Zone files are compared ignoring the SOA serial; each changed dynamic zone is updated with `rndc freeze` → file swap → `.jnl` removal → `rndc thaw` (`reload_zone()`).
- Generates missing secrets (LDAP role-account passwords, `webui_oidc_secret`), renders the 389-DS seed LDIFs, the webui config and the `fabric-agent` unit, copies the webui image build context (`fabric/jinja/webui/build` + `lib/webui` → `/opt/webui/build/app`), and runs `dirsrv.sh seed` when seed files change. `fabric-agent` is restarted (non-blocking) when its unit changes; `webui` is rebuilt if its build context changed and restarted last (non-blocking) when anything of it changed.

### 4. `dns.sh`
**Purpose**: DNS record management workflows.
- Contains the logic for the `--dns-record` and `--remove-dns-record` operations (`do_dns_record()`).
- Interfaces with the `vars.yaml` file to append or remove DNS configurations interactively.
- Reloads the running BIND9 instance to apply changes seamlessly.

### 5. `interactive.py`
**Purpose**: The core `fabricctl` interactive engine.
- Provides categorical editing for all infrastructure variables, featuring strong typing, validation, audit logging, and immutable lock enforcement.
- DNS editor shows full record values (`format_record_value()`) and live sync status by comparing the serial from `rndc zonestatus` to the zone file (`zone_sync_status()`).
- Directly invokes `deploy.py` to synchronize state when edits are applied.

### 6. `manage.sh`
**Purpose**: Legacy CLI wrapper for shell functions.
- Serves as the primary entrypoint for `fabricctl` CLI commands that still rely on shell execution (like `--mint-certs` or TSIG keys).
- Offloads `--interactive` editing and `--apply` deployment duties to the modern `interactive.py` engine.
- Dispatches `--client-cert` (`certs.sh`), `--keycloak-sync` (`keycloak_bootstrap.py`), `--migrate-ldap` (`ldap_migrate.sh`) and `--version` (reads `fabric/VERSION` and `fabric/BUILD`).

### 7. `output.sh`
**Purpose**: Formatting and logging.
- Defines standard, colorized output functions: `info()`, `ok()`, `warn()`, `err()`.
- Standardizes the console output aesthetics across all wrapper scripts to ensure a consistent user experience.

### 8. `package.sh`
**Purpose**: Offline prerequisite staging and installation.
- Orchestrates the `offline.sh` operations.
- Defines the canonical arrays for `CONTROLLER_APT_PACKAGES`, `ANSIBLE_COLLECTIONS`, `TARGET_APT_PACKAGES`, `DOCKER_IMAGES`, and `CONTEXT_IMAGES` (locally built images, `tag|context-dir[|app-dir]`: `fabric/dirsrv:local`, `fabric/webui:local` with `lib/webui` copied in as `app/`).
- Contains `do_package()` which downloads and packages these dependencies into `.tar` or `.zip` bundles for air-gapped deployments.

### 9. `prereqs.sh`
**Purpose**: Prerequisite extraction and loading.
- Used by `setup.sh` to handle the `--prereqs` and `--prereqs-target` arguments.
- Contains `_resolve_prereqs_dir()` which detects if the provided bundle is a zip/tar archive, unpacks it to a temporary directory, and registers a cleanup trap.

### 10. `services.sh`
**Purpose**: Direct execution runner for live systems.
- Replaces legacy Ansible-based live reloads with faster, direct shell/docker commands.
- Contains functions like `run_dns_reload()` which immediately applies configurations to live containers (e.g., executing `rndc reload` inside the BIND9 container).

### 11. `ssh.sh`
**Purpose**: SSH key distribution and trust management.
- Contains `ensure_ssh_access()` which automatically prepares SSH access to a remote host.
- Prompts for a user, generates a local Ed25519 keypair if needed, adds the remote host to `known_hosts`, and copies the public key using `ssh-copy-id`.

### 12. `tsig.sh`
**Purpose**: BIND9 TSIG key management workflows.
- Contains the logic for `--tsig-keys`, `--list-tsig`, and `--remove-tsig` (`do_tsig_keys()`).
- Manages the cryptographic keys used to authorize dynamic DNS updates.

### 13. `vars.sh`
**Purpose**: YAML mutation helpers.
- Contains python-based inline parsers (e.g., `_vars_list_append()`) to dynamically mutate `custom-vars.yaml` and `vars.yaml` without breaking formatting.
- Tries to use `ruamel.yaml` to preserve user comments when appending new items (like DNS records or certificates) and falls back to `PyYAML` if necessary.

### 14. `dirsrv.sh`
**Purpose**: 389 Directory Server helpers (sourceable, or run as `bash dirsrv.sh seed`).
- `dirsrv_wait_healthy()` waits for the `dirsrv` container health check.
- `dirsrv_seed()` runs `/seed/seed.py /seed/*.ldif` inside the container (LDAPI as Directory Manager; source: `fabric/jinja/dirsrv/seed.py`). Entries are added only if missing and modifies only touch differing values; if `seed.py` prints `RESTART_REQUIRED` (a `cn=config` change), the `ldap` service is restarted.

### 15. `ldap_migrate.sh` / `ldap_migrate.py`
**Purpose**: One-time OpenLDAP → 389-DS migration (`fabricctl --migrate-ldap [old_dir]`).
- `ldap_migrate.sh [old_dir] [old_image]` copies the old `data/` + `config/` (default `/opt/openldap`), exports it with `slapcat` via `osixia/openldap:1.5.0`, backs up the current 389-DS database (`dsconf backend export` → `/opt/dirsrv/data/ldif/pre-migrate-*.ldif`), merges, then imports the merged LDIF (`dsconf backend import`), rebuilds `memberOf` and re-runs `keycloak_bootstrap.py`. Import is used because 389-DS regenerates `entryUUID` on every LDAP add but keeps it on import.
- `ldap_migrate.py <old.ldif> <current.ldif> <out.ldif>` (runs in the container) merges: entries already in 389-DS win (suffix, OUs, seeded role accounts), `cn=admin` is dropped, operational attributes are stripped except `entryUUID`, password hashes are kept, `member` values are merged into existing groups. Prints `NOTHING_TO_IMPORT` when there is nothing new, so re-running is safe.

### 16. `keycloak_bootstrap.py`
**Purpose**: Idempotent Keycloak configuration over the admin REST API (TLS pinned to the core root CA; no secrets on argv). Called by playbook 09 and `fabricctl --keycloak-sync`.
- Realm with brute-force protection; LDAP federation to 389-DS (`rhds`, `ldaps://<hostname_ldap>:3636`, `entryUUID`; updates an existing `OpenLDAP` provider in place); group mapper + sync.
- Realm role `webui_admin_role` → group `webui_admin_group`; confidential client `fabric-webui` (PKCE S256, exact redirect URI, `fullScopeAllowed: false`, roles in ID token); flow `fabric-webui-mfa` (TOTP required) bound to that client only.

### 17. `webui/`
**Purpose**: The webui management UI (Python stdlib + `jinja2`), baked into the unprivileged `webui` container image and serving a unix socket behind nginx. Holds no privilege; every operation goes to `fabric-agent`. See [webui.md](webui.md).
- `server.py` — HTTP server and security gates (client-cert issuer/CN/fingerprint, sessions, CSRF/Origin); config from `/config/webui.json` (host `/opt/webui/config/webui.json`). Returns `503` when the agent is unreachable.
- `oidc.py` — OIDC authorization code + PKCE client; verifies ID token signature (RS256/JWKS), issuer, audience, azp, expiry, nonce.
- `tlsclient.py` — HTTPS client pinned to the core root CA (reaches Keycloak by container IP, verifies by hostname).
- `agentclient.py` — JSON client for the `fabric-agent` socket (`agent_socket`, `/agent/agent.sock`); same function names the UI used before (imported as `actions`). Raises `ValidationError` (agent `400`) or `AgentError` (agent down / other error).
- `views.py` — autoescaped Jinja2 templates; no inline script/style (strict CSP).

### 18. `agent/`
**Purpose**: `fabric-agent`, the privileged half of the web UI. Runs on the host as root (systemd `fabric-agent`, sandboxed, no network listener) and serves a fixed JSON API on `/opt/webui/agent/agent.sock` (`0660 root:<webui gid>`). See [webui.md](webui.md#privilege-separation).
- `server.py` — unix-socket HTTP server; `SO_PEERCRED` check on every connection (webui uid + root only); routes `GET /v1/version|services|zones|zones/<key>|audit`, `POST /v1/zones/<key>/records`, `/v1/zones/<key>/records/delete`, `/v1/apply`, `/v1/events` (`LOGIN`/`LOGOUT`/`LOGIN_DENIED`); everything else `404`. Validates actor names, 64 KiB body limit.
- `actions.py` — service status, DNS zone/record add/delete, apply (same code path as `fabricctl --apply`), audit log (`/opt/fabric/archive/audit.log`); edits and applies take `/opt/fabric/config/.webui.lock`.
