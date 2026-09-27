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
- [Interactive Menu Categories](#interactive-menu-categories)
  - [DNS Configuration](#dns-configuration)
  - [Mint Certificates](#mint-certificates)
  - [TSIG Keys (RFC2136)](#tsig-keys-rfc2136-dynamic-updates)
  - [Landing Page Links](#landing-page-links)
- [Lifecycle Commands](#lifecycle-commands)
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
- If the **webui** config, app code or Dockerfile changes, the `webui` image is rebuilt (if needed) and the container restarted last (queued with `--no-block`, so an apply started from webui completes). If the `fabric-agent` unit changes, `fabric-agent` is restarted (also queued).
- A full container restart (`docker compose down/up` via systemctl) is ONLY triggered if immutable service definitions (like `docker-compose.yml` or the systemd `.service` wrapper) or service-specific config files (like StepCA templates) actually change their rendered contents.

```bash
sudo fabricctl --apply
```

#### `--update-containers`
Pulls the latest images for all deployed containers and recreates them. The 389-DS and webui images are built locally, so for `dirsrv` and `webui` this runs `docker compose build --pull` instead — a fresh `debian:trixie-slim` base plus the current Debian packages (`389-ds-base`; `python3`, `python3-jinja2`, `openssl`), which is how their security updates arrive. Each step is protected by a timeout (pull 300 s, build 900 s) to prevent indefinite hangs if registries or mirrors are slow.

```bash
sudo fabricctl --update-containers
```

#### `--version`
Print the version from `fabric/VERSION` plus the build stamp in `fabric/BUILD` (git commit, `-dirty` if the tree had local changes, and UTC build time — written by `setup.sh` on each run).

```bash
sudo fabricctl --version
```

#### `--client-cert <user>`
Mint a webui admin client certificate (same as `fabricctl client-cert <user>`). The CN is `<user>` and **must equal the Keycloak username**. Issued offline by the Step-CA intermediate (RSA 3072, `webui_client_cert_days`, default 365), bundled with the chain into `~/fabric-admin/<user>.p12` (home of the account that ran `sudo`, mode `0600`) with a generated password that is shown once. The private key exists only inside the `.p12`. Setup already does this for the first admin — see [webui.md](webui.md#first-time-setup).

```bash
sudo fabricctl --client-cert jdoe
```

#### `--keycloak-sync`
Re-run `keycloak_bootstrap.py`: realm, LDAP federation to 389-DS, group mapper and sync, `fabric-admin` role → `admins` group, the `fabric-webui` OIDC client and its TOTP flow. Idempotent — use after changing `webui_*` vars or to repair drift made in the admin console.

```bash
sudo fabricctl --keycloak-sync
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

#### TSIG Keys (RFC2136 dynamic updates)

TSIG keys let other systems update DNS over RFC2136 — typically a reverse proxy obtaining Let's Encrypt certificates with DNS-01, like nginx-proxy-manager's certbot `rfc2136` plugin. A key is a `tsig_keys` entry in the vars; its secret lives only in `fabric-secrets.yml` (`0600`). From them fabric renders the BIND key, its `update-policy` grants and an `rfc2136.ini` for the client; nothing edits the rendered BIND files by hand, so keys survive every apply and setup re-run.

```yaml
tsig_keys:
- name: npm                   # nginx-proxy-manager
  records: [npm, shelfmark]   # may only set _acme-challenge.npm.<domain> and _acme-challenge.shelfmark.<domain>
  secret: "base64..."         # OPTIONAL: keep an existing key (its clients keep working unchanged)
- name: acme_nas-proxy
  record_types: [TXT, A]      # no records: may update these types anywhere in the zone (zonesub)
```

| Field | Default | Meaning |
|---|---|---|
| `name` | — | Key name the client uses (`dns_rfc2136_name`) |
| `secret` | generated once | Base64 secret. Given in the vars, it is moved into `fabric-secrets.yml` and removed from the vars files; it always wins over a stored one |
| `algorithm` | `hmac-sha256` | `hmac-sha256/384/512/224`, `hmac-sha1`, `hmac-md5` |
| `domain` | the fabric domain | Zone the key may update |
| `records` | — | Hosts allowed a DNS-01 challenge: `grant <key> name _acme-challenge.<record>.<zone>. <types>` |
| `record_types` | `[TXT]` | Record types it may change |
| `primary` | — | The zone's own ACME key: `grant <key> subdomain _acme-challenge <types>` |
| `out` | `/opt/<name>/rfc2136.ini` | Credentials file for the client (`0600`): server = `host_ip`, port = `bind_dns_port`, key, secret, algorithm |

Without `records` or `primary`, the key gets `zonesub` for its `record_types`.

```bash
sudo fabricctl tsig list
sudo fabricctl tsig add npm --record npm --record shelfmark              # new secret -> /opt/npm/rfc2136.ini
sudo fabricctl tsig add npm --record npm --secret-file /root/npm.secret   # keep an existing key's secret
sudo fabricctl tsig remove npm
```

`add` and `remove` update the vars and secrets and apply at once (BIND reloads its configuration). A secret is never taken on the command line: `--secret-file` or `--secret-prompt`.

**Keeping an existing key (rebuilding a host):** put its `name`, `records` and `secret` in the vars file you give `fabricctl setup --file`, with the same `domain`. BIND on the new host then accepts the same client configuration unchanged (server = `host_ip`, port 53).

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

The following chart outlines the memory footprint and CPU impact of the deployed applications. When `host_ram_capacity` is set to a value between 3 and 4, the infrastructure automatically enforces Docker Compose memory constraints (389-DS: `256M` at 3 GB, `384M` at 4 GB; webui: `96M`) to prevent these services from exceeding the host's physical memory boundaries.

| Service | Startup (Peak RAM) | Idle (RAM) | Typical Usage | CPU Impact |
|---------|--------------------|------------|---------------|------------|
| Keycloak | 800MB – 1.2GB | 500MB – 700MB | 800MB – 1.2GB | High (during auth) |
| Postgres | 150MB | 80MB | 100MB – 200MB | Low |
| 389-DS | 150MB – 250MB | 60MB – 120MB | 100MB – 250MB | Very Low |
| webui (container) + fabric-agent (host) | 30MB + 20MB | 20MB – 30MB each | 20MB – 40MB each | Minimal |
| AdGuardHome | 100MB | 30MB – 50MB | 60MB – 120MB | Low (sustained) |
| BIND9 | 60MB | 30MB – 40MB | 40MB – 80MB | Very Low |
| Nginx | 20MB | 5MB – 10MB | 15MB – 40MB | Very Low |
| Step-ca | 50MB | 15MB – 25MB | 30MB – 50MB | Minimal |

---

## Lifecycle Commands

Install, repair and removal are `fabricctl` subcommands (Python, `fabric/lib/fabriclib/setup/`). All are idempotent. See [install.md](install.md#run-the-installer) for options and the step list.

| Command | What it does |
|---|---|
| `sudo fabricctl setup [--file vars.yaml]` | Install or re-converge. Re-run after changing settings. |
| `sudo fabricctl setup --step <name>` | Run one step, e.g. `--step firewall` after editing `security.firewall_allow` |
| `sudo fabricctl doctor` | End-to-end checks of the running install (the `verify` step) |
| `sudo fabricctl tsig list/add/remove` | TSIG keys for RFC2136 clients — see [TSIG Keys](#tsig-keys-rfc2136-dynamic-updates) |
| `sudo fabricctl client-cert <user>` | Web UI client certificate for another admin (`~/fabric-admin/<user>.p12`) |
| `sudo fabricctl certs [--force]` | Renew service certificates that are missing, expiring within 30 days or missing a name (`--force`: all of them); restarts only the services whose certificates changed |
| `sudo fabricctl reinstall` | Uninstall + setup, keeping config, secrets, the CA and certificates. Directory users/groups and Keycloak's database are **not** kept; the first admin is re-created with a new login kit |
| `sudo fabricctl uninstall` | Remove fabric's containers, images, network, units, accounts and `/opt` directories (nothing else) |

---

## Service Ports

| Port | Proto | Handler | Backend |
|------|-------|---------|---------|
| 80 | TCP | nginx | health check · ACME passthrough · HTTPS redirect |
| 389 | TCP | nginx | `dirsrv:3389` (TCP passthrough; 389-DS requires StartTLS before bind) |
| 443 | TCP | nginx | `step-ca:9000` · `bind9:8053` (`/dns-query`) · Keycloak · webui (`mgr.<domain>`, mTLS → `/opt/webui/run/web.sock`; the webui container publishes no ports, fabric-agent has no network listener) |
| 636 | TCP | nginx | `dirsrv:3636` (TCP passthrough; LDAPS terminated by 389-DS) |
| `bind_dns_port` | TCP + UDP | bind9 | DNS for the LAN (`host_ip:bind_dns_port` → container 53); default `53` |
| `bind9_doh_port` | TCP | bind9 | plain-HTTP DoH; default `8053` |
| `stepca_port` | TCP | step-ca | internal HTTPS; default `9000` |

> `bind_dns_port` (default `53`) is the Docker host port mapped to BIND9's internal port 53 (`bind_dns_port:53`). BIND9 only listens on port 53 inside the container; Docker forwards host traffic on `bind_dns_port` to it. The default port is 53 natively, allowing BIND9 to answer standard DNS queries directly. If you install the `home-core` add-on, this port is shifted to `5353` automatically to allow AdGuard Home to claim port 53 instead.
