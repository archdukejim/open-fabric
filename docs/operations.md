# Operations

## Live Configuration Changes (`fabricctl`)

Use `fabricctl` (the global wrapper powered by the interactive Python engine) for post-install changes to DNS records, TSIG keys, certificates, and infrastructure variables — no full redeploy needed. Run it **on the target machine** (requires root / sudo). The same DNS and apply operations are also available in the browser through webui — see [webui.md](webui.md).

### Table of Contents
- [Live Configuration Management (`fabricctl`)](#live-configuration-management-fabricctl)
  - [`--interactive`](#--interactive)
  - [`--print`](#--print)
  - [`--apply`](#--apply)
  - [`--update-containers`](#--update-containers)
  - [`--version`](#--version)
  - [`--client-cert <user>`](#--client-cert-user)
  - [`--keycloak-sync`](#--keycloak-sync)
  - [`--migrate-ldap [old_dir]`](#--migrate-ldap-old_dir)
- [Interactive Menu Categories](#interactive-menu-categories)
  - [DNS Configuration](#dns-configuration)
  - [Mint Certificates](#mint-certificates)
  - [TSIG Keys](#tsig-keys)
  - [Landing Page Links](#landing-page-links)
- [Migrating from OpenLDAP](#migrating-from-openldap)
- [Ansible Tags Reference (Initial Install Only)](#ansible-tags-reference-initial-install-only)
- [Service Ports](#service-ports)

---

### Live Configuration Management (`fabricctl`)

The infrastructure variables defined in `vars.yaml` can be managed directly via `fabricctl` using the interactive menu system or by editing the YAML manually. 

#### `--interactive`
Launch the interactive configuration menu. This will display categories of variables in `vars.yaml`, allowing you to select and modify them one by one. Immutable variables are protected from modification to prevent breaking the deployment. Changes are audit-logged, and applying changes to network variables will prompt a warning before restarting services.

```bash
sudo fabricctl --interactive
```

#### `--print`
Print the current contents of `vars.yaml` in a colorized, human-readable format.

```bash
sudo fabricctl --print
```

#### `--apply`
Apply any manual changes made directly to `vars.yaml`. `fabricctl` leverages the native Python `deploy.py` engine to compare the file against the running configuration, directly render Jinja2 templates, and selectively reload or restart only the affected systemd-managed services. 

**Intelligent Restarts:** `deploy.py` tracks exact file modifications.
- If only `nginx/www/...` templates change, Nginx natively live-reads the files. No restart or reload is performed.
- If `bind9` configuration changes, BIND9 gets `rndc reconfig`; if `nginx` configuration changes, `nginx -s reload`.
- **DNS zones** are compared ignoring the SOA serial, so only zones whose records actually changed are touched. Forward zones are dynamic (they carry an `update-policy`), so each changed zone is updated with `rndc freeze` → swap the zone file → delete the stale `.jnl` → `rndc thaw` (static zones get `rndc reload <zone>`). Non-disruptive; dynamic updates made since the last apply (e.g. ACME TXT records) are discarded for that zone.
- If a **389-DS seed file** (`/opt/dirsrv/seed/*.ldif`) changes, it is applied live with `dirsrv.sh seed`; the `ldap` service is restarted only if `cn=config` changed.
- If the **webui** config or unit changes, `webui` is restarted (queued, so an apply started from webui completes).
- A full container restart (`docker compose down/up` via systemctl) is ONLY triggered if immutable service definitions (like `docker-compose.yml` or the systemd `.service` wrapper) or service-specific config files (like StepCA templates) actually change their rendered contents.

```bash
sudo fabricctl --apply
```

#### `--update-containers`
Pulls the latest images for all deployed containers and recreates them. The 389-DS image is built locally, so for `dirsrv` this runs `docker compose build --pull` instead — a fresh `debian:trixie-slim` base plus the current Debian `389-ds-base` packages, which is how its security updates arrive. Each step is protected by a timeout (pull 300 s, build 900 s) to prevent indefinite hangs if registries or mirrors are slow.

```bash
sudo fabricctl --update-containers
```

#### `--version`
Print the version from `fabric/VERSION` plus the build stamp in `fabric/BUILD` (git commit, `-dirty` if the tree had local changes, and UTC build time — written by `setup.sh` on each run).

```bash
sudo fabricctl --version
```

#### `--client-cert <user>`
Mint a webui admin client certificate. The CN is `<user>` and **must equal the Keycloak username**. Issued offline by the Step-CA intermediate (RSA 3072, 365 days), bundled with the chain into a password-protected `~/<user>-fabricctl.p12` (home of `SUDO_USER`, mode `0600`). The private key exists only inside the `.p12`. See [webui.md](webui.md).

```bash
sudo fabricctl --client-cert jdoe
```

#### `--keycloak-sync`
Re-run `keycloak_bootstrap.py`: realm, LDAP federation to 389-DS, group mapper and sync, `fabric-admin` role → `admins` group, the `fabric-webui` OIDC client and its TOTP flow. Idempotent — use after changing `webui_*` vars, after an LDAP migration, or to repair drift made in the admin console.

```bash
sudo fabricctl --keycloak-sync
```

#### `--migrate-ldap [old_dir]`
One-time import of an old OpenLDAP deployment into 389-DS (default `old_dir`: `/opt/openldap`). See [Migrating from OpenLDAP](#migrating-from-openldap).

```bash
sudo fabricctl --migrate-ldap
```

---

### Interactive Menu Categories

All granular modifications are now managed within the unified `--interactive` menu system rather than via individual command-line flags. 

#### DNS Configuration

Add, modify, or remove records in BIND9 zones without a full redeploy via the interactive menu. Supported record types include `A`, `AAAA`, `CNAME`, `MX`, `TXT`, and `SRV`.

**DNS Sync Status & Actions:**
When entering a specific zone, the menu compares the serial BIND9 is serving (`rndc zonestatus`) with the serial in the deployed `db.<zone>` file:
- `IN SYNC (serial N)`: BIND9 serves the deployed file (or newer, e.g. after dynamic updates).
- `OUT OF SYNC (serving serial N, file has M; run 'l')`: the file on disk is newer than what BIND9 serves.
- `NOT LOADED in BIND9` / `? BIND9 not reachable`: the zone failed to load or the container is down.

Records are listed with their full value (`A`/`AAAA` ip, `CNAME` target, `MX` priority + exchange, `TXT` text, `SRV` priority/weight/port/target). Records without a name (or named `None`) are shown as `(missing name)`, rejected on entry, and filtered out at render time.

You have two powerful options to apply your pending `vars.yaml` modifications directly from the menu:
- **`l` (Live update):** Runs the same apply as `fabricctl --apply`: each changed zone is frozen, its file swapped, the `.jnl` removed and the zone thawed. *Non-disruptive to DNS resolution.*
- **`f` (Force update):** Stops BIND9, deletes `db.<zone>` and its `.jnl`, then runs the apply, which rewrites the zone and starts BIND9 again. *Warning: Disruptive — DNS is down while it runs.*

Changes edit `vars.yaml` and re-render forward and reverse zone files natively using Jinja2. Rendered files are written to `/opt/bind9/data/` with bind ownership. **Reverse zones are auto-generated** based on `/24` subnets found in `A` records.

`dns:` zone key uses the actual domain string (the `dynamic_zone_var` placeholder is already resolved to `domain` at install time):

```yaml
dns:
  yourdomain.internal:
    zone_authority: true    # emit NS A record pointing to host_ip
    tsig: acme_dns-01
    A:
    - { name: myserver, ip: 10.0.3.99 }
    CNAME:
    - { name: app, canonical: myserver }
    TXT:
    - { name: myserver, text: "v=spf1 -all" }
```

#### Mint Certificates

Mint offline or ACME-based TLS certificates for services outside this stack (NAS apps, VMs, etc.) via the interactive menu. `vars.yaml` structure for extra certificates:

```yaml
extra_certs:
- cn: nas-apps.internal
  sans: [jellyfin.internal, sonarr.internal]
  days: 365
  kty: RSA           # RSA | EC | OKP  (default: RSA)
  size: 4096         # RSA: 2048/3072/4096  EC: 256/384  (default: 4096)
  out_dir: /srv/certs
```

**Offline mode:** signed directly by Step-CA using the internal `leaf.tpl` x509 template — no ACME required.

**ACME mode:** issued via Step-CA's ACME provisioner with DNS-01 validation against BIND9 using the primary TSIG key. All core service certs (`dns.internal`, `ldap.internal`, `ca.internal`) are offline Step-CA certs issued at install time.

#### TSIG Keys

TSIG keys grant named DNS update rights to external services (NAS, reverse proxies, other hosts) for specific hostnames only. Manage keys (Add, Modify, Delete) directly through the interactive menu.

All TSIG keys are managed in the `tsig_keys` list in `vars.yaml`. Each key carries a `record_types` list that drives its `update-policy` grant in BIND9:

- `primary: true` + `record_types` → `grant key subdomain _acme-challenge <types>` (ACME DNS-01 scope)
- no `primary` + `record_types` → `grant key zonesub <types>` (zone-wide update rights for those types)

```yaml
tsig_keys:
- name: acme_dns-01       # primary ACME key — managed by installer
  algorithm: hmac-sha256
  domain: '{{ domain }}'
  primary: true
  record_types: [TXT]     # may update _acme-challenge TXT records
- name: acme_nas-proxy    # extra key — applied by fabricctl
  algorithm: hmac-sha256
  domain: '{{ domain }}'
  record_types: [TXT, A]  # zone-wide TXT and A update rights
```

All TSIG key names are also collected into a `tsig-updaters` ACL in `named.conf.acl` so they can be referenced in other BIND9 directives. Each key generates:
- An entry in `named.conf.keys` with a random 256-bit secret
- `update-policy` grant(s) in `named.conf.zones` based on `record_types`
- A `rfc2136.ini` credentials file for the consuming service

#### Landing Page Links

The landing page provides a grid of quick links for the infrastructure. You can add, modify, or delete these links dynamically using the interactive menu. 

All custom links are saved in `link-vars.yaml` and are deployed alongside the normal variables. They natively evaluate Jinja variables such as `{{ domain }}` to ensure links stay accurate even if the base domain changes.

```yaml
links:
  - name: Adguard Home
    link: "adguard.{{ domain }}"
  - name: Keycloak (Admin)
    link: "sso.{{ domain }}/admin"
```

---

## Resource Utilization

The following chart outlines the memory footprint and CPU impact of the deployed applications. When `host_ram_capacity` is set to a value between 3 and 4, the infrastructure automatically enforces Docker Compose memory constraints (389-DS: `256M` at 3 GB, `384M` at 4 GB) to prevent these services from exceeding the host's physical memory boundaries.

| Service | Startup (Peak RAM) | Idle (RAM) | Typical Usage | CPU Impact |
|---------|--------------------|------------|---------------|------------|
| Keycloak | 800MB – 1.2GB | 500MB – 700MB | 800MB – 1.2GB | High (during auth) |
| Postgres | 150MB | 80MB | 100MB – 200MB | Low |
| 389-DS | 150MB – 250MB | 60MB – 120MB | 100MB – 250MB | Very Low |
| webui | 30MB | 20MB – 30MB | 20MB – 40MB | Minimal |
| AdGuardHome | 100MB | 30MB – 50MB | 60MB – 120MB | Low (sustained) |
| BIND9 | 60MB | 30MB – 40MB | 40MB – 80MB | Very Low |
| Nginx | 20MB | 5MB – 10MB | 15MB – 40MB | Very Low |
| Step-ca | 50MB | 15MB – 25MB | 30MB – 50MB | Minimal |

---

## Upgrading from core-template

fabric was previously named core-template. Re-running `sudo ./setup.sh` from a fabric checkout migrates an existing install in place (playbook `00b-migrate-from-core.yml`, a no-op on fresh or already-migrated hosts):

| Before | After |
|---|---|
| `/opt/core` | `/opt/fabric` |
| `config/core-secrets.yml` (on the target and in the repo root) | `config/fabric-secrets.yml` |
| vars key `core_subnet` | `fabric_subnet` (the old key is still honoured) |
| Docker network `core_net` | `fabric_net` (same subnet; containers are recreated on start) |
| `/usr/local/bin/core-mgr` | `/usr/local/bin/fabricctl` — `core-mgr` remains as an alias for one release |
| `/etc/systemd/resolved.conf.d/core-dns.conf` | `fabric-dns.conf` |

Services are stopped briefly while the Docker network is replaced. Service data directories (`/opt/nginx`, `/opt/bind9`, `/opt/stepca`, ...) are not touched.

## Migrating from OpenLDAP

Deployments before 1.5.0 ran `osixia/openldap` from `/opt/openldap`. The upgrade deploys 389-DS in `/opt/dirsrv` with a fresh tree and fresh role-account passwords; user and group data is moved with `--migrate-ldap`.

1. **Back up** `/opt/openldap` (and `/opt/fabric/config/fabric-secrets.yml`), e.g. `sudo tar -czf ~/openldap-backup.tgz -C /opt openldap`.
2. **Deploy** the new version: `sudo ./setup.sh`. `/opt/openldap` is left untouched by the upgrade (snapshots and uninstall still include it). If a stopped `openldap` container still exists, it can be removed with `docker rm openldap`.
3. **Migrate**: `sudo fabricctl --migrate-ldap [old_dir]`.
   - Runs `slapcat` against a *copy* of the old `data/` and `config/` using the `osixia/openldap:1.5.0` image (must be pullable or already loaded).
   - Exports the current 389-DS database to `/opt/dirsrv/data/ldif/pre-migrate-<timestamp>.ldif` (your rollback point), merges the OpenLDAP entries into it and **imports** the result with `dsconf backend import`. An import is used rather than LDAP adds because 389-DS always generates a new `entryUUID` on add (and refuses to modify it), but keeps it on import.
   - Merge rules: entries already in 389-DS (suffix, OUs, seeded role accounts) win; `entryUUID` and password hashes are preserved (389-DS re-hashes to PBKDF2-SHA512 on next bind); missing group `member` values are merged; osixia's `cn=admin` is dropped, including from group membership; `memberOf` is rebuilt afterwards.
   - Re-runs the Keycloak bootstrap (if `keycloak` is running), which repoints the existing `OpenLDAP` federation provider to 389-DS in place, so federated users keep their Keycloak links.
   - Safe to re-run.
4. **Verify**: log in to Keycloak (and webui) as a migrated user; check group membership in the Keycloak admin console. To roll back the directory, import the `pre-migrate-*.ldif` backup: `docker exec dirsrv dsconf localhost backend import userroot /data/ldif/pre-migrate-<timestamp>.ldif`.
5. **Remove** the old data once satisfied: `sudo rm -rf /opt/openldap`.

> Role accounts (`super_admin`, `group_admin`, `user_creator_admin`, `user_modifier_admin`, `keycloak_admin`) are **not** migrated — they now have per-account generated passwords in `fabric-secrets.yml`. Update any client that used the old shared password.

---

## Ansible Tags Reference (Initial Install Only)

> [!NOTE]
> Ansible is now strictly used for the **initial deployment and bootstrapping** of the infrastructure. For any day-2 operations (e.g. changing configurations, minting certificates, updating DNS), use the Python-based `fabricctl` interactive CLI instead.

The full playbook (`fabric/playbooks/fabric-config.yml`) is an `import_playbook` entry point composed of individual playbooks in `fabric/playbooks/`. During an initial install, each section can be run directly:

```bash
# Via setup.sh (recommended — handles SSH key setup and sudo)
sudo ./setup.sh --custom --tags <tag>

# Or directly with ansible-playbook
ansible-playbook fabric/playbooks/09-start-and-configure.yml -e target_host=fabric
```

| Tag | Section | Playbook | What it does |
|-----|---------|----------|-------------|
| `prereqs`,`validation` | 00 | `00-controller-check.yml` | Validate controller environment |
| *(always)* `handle-vars`, `render-jinja` | 01 | `01-gen-vars-and-render-jinja.yml` | Generate CA password + TSIG secrets into `fabric-secrets.yml` (idempotent); Merge all vars + secrets; render every template to `/tmp/fabric-render` |
| `users` | 03 | `03-target-service-accounts.yml` | Create service accounts (nginx, bind, step, ldap) |
| `file-structure`, `bind9`, `stepca`, `nginx`, `add-ldap`, `dirsrv`, `webui`, `systemd` | 04 | `04-target-file-structure.yml` | Create directory tree; deploy configs, stepca dirs, bind9 runtime dirs, 389-DS seed files, webui config + unit; create `fabricctl` global wrapper |
| `network`, `firewall` | 05 | `05-target-network.yml` | Harden systemd-resolved; configure UFW (LAN allow-list) |
| `pki`, `stepca` | 06 | `06-configure-stepca.yml` | Sign intermediate CA CSR (if deployed); initialize and configure step-ca |
| `pki`, `bootstrap` | 07 | `07-bootstrap-containers.yml` | Bootstrap bind9+step-ca containers safely |
| `pki`, `mint-certs` | 08 | `08-mint-service-certs.yml` | Mint BIND9 TLS, service certs (incl. `mgr.<domain>`), and `extra_certs`; install 389-DS TLS files and the webui client-CA bundle |
| `start`, `configure`, `keycloak` | 09 | `09-start-and-configure.yml` | Start full stack; seed 389-DS; run `keycloak_bootstrap.py`; start `webui` |
| `verify`, `deploy-checks`, `cleanup` | 10 | `10-deploy-checks-and-cleanup.yml` | dig DNS; check nginx/HTTPS; LDAP role-account binds, plaintext-bind refusal, LDAPS cert; webui socket + `400` without client cert; export 30s logs; drop stack if `no_start` |

---

## Service Ports

| Port | Proto | Handler | Backend |
|------|-------|---------|---------|
| 53 | TCP + UDP | nginx | `bind9:53` (container-to-container) |
| 80 | TCP | nginx | health check · ACME passthrough · HTTPS redirect |
| 389 | TCP | nginx | `dirsrv:3389` (TCP passthrough; 389-DS requires StartTLS before bind) |
| 443 | TCP | nginx | `step-ca:9000` · `bind9:8053` (`/dns-query`) · Keycloak · webui (`mgr.<domain>`, mTLS → `/opt/webui/run/web.sock`) |
| 636 | TCP | nginx | `dirsrv:3636` (TCP passthrough; LDAPS terminated by 389-DS) |
| `bind_dns_port` | TCP + UDP | bind9 | host-facing (mapped `bind_dns_port:53`); default `53` |
| `bind9_doh_port` | TCP | bind9 | plain-HTTP DoH; default `8053` |
| `stepca_port` | TCP | step-ca | internal HTTPS; default `9000` |

> `bind_dns_port` (default `53`) is the Docker host port mapped to BIND9's internal port 53 (`bind_dns_port:53`). BIND9 only listens on port 53 inside the container; Docker forwards host traffic on `bind_dns_port` to it. The default port is 53 natively, allowing BIND9 to answer standard DNS queries directly. If you install the `home-core` add-on, this port is shifted to `5353` automatically to allow AdGuard Home to claim port 53 instead.
