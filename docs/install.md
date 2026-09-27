# Setup and Installation

fabric installs on the host it runs on: clone the repo there and run `setup.sh`, which hands over to `fabricctl setup`. There is no controller machine and no Ansible.

### Table of Contents
- [Requirements](#requirements)
- [Configure vars](#configure-vars)
  - [Customization Checklist](#customization-checklist)
- [Generate PKI (optional, before install)](#generate-pki-optional-before-install)
- [Run the Installer](#run-the-installer)
  - [The default plan](#the-default-plan)
  - [Non-interactive install](#non-interactive-install)
  - [Options](#options)
  - [Steps](#steps)
- [Deployed Structure](#deployed-structure)
- [Upgrading from core-template / OpenLDAP](#upgrading-from-core-template--openldap)
- [Reinstall / Uninstall](#reinstall--uninstall)

---

## Requirements

- Ubuntu 24.04 LTS (Debian 12+ works), **amd64 or arm64** (Raspberry Pi 4/5 included)
- 3 GB RAM or more with Keycloak (the default); 2 GB without it
- cgroup v2 with the memory controller (Raspberry Pi: add `cgroup_enable=memory` to `/boot/firmware/cmdline.txt` if `preflight` asks for it)
- Nothing else listening on the LAN IP's ports 53, 80, 443, 636, 853

Setup installs what it needs from apt: `openssl`, `ca-certificates`, `curl`, `gnupg`, `ufw`, `iptables`, `dnsutils`, `ldap-utils`, `python3-yaml`, `python3-jinja2`, and Docker Engine (`docker-ce`, `containerd.io`, compose and buildx plugins) from Docker's own apt repository if Docker is missing.

## Configure vars

Setup needs five values: `domain`, `hostname`, `host_ip`, `lan_cidr`, `lan_gateway`. Run interactively, it asks for any that are missing and suggests values detected from the default route. For everything else, start from the template:

```bash
cp custom-vars-tpl.yml custom-vars.yaml
```

Settings are read in this order, later wins:

1. an existing install's `/opt/fabric/config/vars.yaml` (so re-running setup never loses DNS records added in the web UI or editor)
2. `--file <vars.yaml>`, or, on a fresh install only, `custom-vars.yaml` in the checkout
3. answers to prompts

The merged result is saved as `/opt/fabric/config/fabric.yaml`. Secrets (CA password, TSIG secrets, Directory Manager and per-role LDAP passwords, Keycloak credentials, the web UI's OIDC client secret) are generated on the first run into `/opt/fabric/config/fabric-secrets.yml` (`0600`) and kept on every re-run. They never appear on a command line.

Minimum `custom-vars.yaml`:

```yaml
domain: home.arpa               # your internal domain (RFC 8375)
hostname: fabric
host_ip: 10.0.3.53              # this host's LAN IP
lan_cidr: 10.0.0.0/22           # your LAN subnet
lan_gateway: 10.0.0.1

# ── DNS RECORDS ─────────────────────────────────────────────────────────────
# Zone key must be the static placeholder 'dynamic_zone_var'.
# Templates resolve it to the 'domain' value at render time.
dns:
  dynamic_zone_var:
    zone_authority: true        # emit NS A record pointing to host_ip
    tsig: acme_dns-01           # primary TSIG key for this zone
    A:
    - { name: nas,  ip: 10.0.3.10 }
```

Key tunables with their defaults:

| Variable | Default | Description |
|----------|---------|-------------|
| `bind_dns_port` | `53` | Host port (on `host_ip`) mapped to BIND9's port 53 — the LAN's DNS port |
| `bind9_doh_port` | `8053` | BIND9 plain-HTTP DoH port (nginx terminates TLS) |
| `stepca_port` | `9000` | Step-CA HTTPS port |

> BIND9 answers DNS itself: Docker publishes `host_ip:bind_dns_port` → the container's port 53 (TCP and UDP). Binding to `host_ip` rather than `0.0.0.0` avoids a conflict with `systemd-resolved` on loopback. DNS-over-HTTPS goes through nginx (`https://dns.<domain>/dns-query` → `bind9:8053`); DNS-over-TLS (853) is not exposed yet.

### Customization Checklist

- [ ] `domain`, `hostname`, `host_ip`, `lan_cidr`, `lan_gateway`
- [ ] `friendly_name` — used in the CA name
- [ ] `system_timezone` — IANA timezone string
- [ ] `dns_server` — upstream DNS used during bootstrap (only used when `use_host_dns: false`; defaults to using the host's existing resolver)
- [ ] `acme_email` — email for ACME registration
- [ ] `ca_name`, `cert_country`, `cert_org` — CA subject fields
- [ ] `byoc` / `ca_crt_path` / `ica_crt_path` — bring your own offline root instead of a generated one
- [ ] `dns:` block — A and CNAME records for your hosts
- [ ] `ldap_groups` / `ldap_organizational_units` — directory structure
- [ ] `install_ldap` / `install_keycloak` / `install_webui` — see [the default plan](#the-default-plan) and [webui.md](webui.md)
- [ ] `security.firewall` / `security.firewall_allow` / `security.docker_daemon_hardening`
- [ ] `tsig_keys` — add non-primary entries for external services that need DNS update rights (optional)
- [ ] `bind_dns_port` — change from `53` only if another DNS server must keep port 53 on `host_ip`
- [ ] `webui_admin_user` — the first web UI admin setup creates (default: the account that ran `sudo`)
- [ ] `image_nginx` / `image_bind9` / `image_stepca` / `image_dirsrv` — override to pin images to specific digests or a local registry (optional)

---

## Generate PKI (optional, before install)

Certificates (such as the ones generated from our standalone [private-root-ca](https://github.com/private-root-ca) repository) are optional.

If you choose to use an offline Root CA to sign your core TLS infrastructure, generate the root and intermediate certificates offline on a secure machine, and never deploy the root key to the target. Then set:

```yaml
byoc: true
ca_crt_path: /path/to/my/offline-pki/output/root_ca.crt
ica_crt_path: /path/to/my/offline-pki/output/intermediate_ca.crt
# ica_key_path defaults to ica_crt_path with .key
```

The `pki` step checks these files, installs them into Step-CA and verifies the chain.

---

## Run the Installer

```bash
git clone https://github.com/archdukejim/fabric.git && cd fabric
sudo ./setup.sh
```

`setup.sh` only makes sure Python's YAML and Jinja2 are present, then runs `fabricctl setup`. Once installed, run `sudo fabricctl setup` from anywhere. Setup is idempotent: change a setting and run it again; finished steps are quick, and certificates are only re-issued when missing, expiring within 30 days, or missing a name.

### The default plan

Every default is the hardened choice. Setup shows the plan and asks **[P]roceed, [A]dvanced, or [Q]uit**. Advanced walks each item and states what relaxing it costs.

| Setting | Default | Relaxing it means |
|---|---|---|
| `security.firewall` | on | UFW default-deny; fabric's ports from the LAN only, also enforced for Docker-published ports (`DOCKER-USER`, re-applied at boot by `fabric-firewall.service`). SSH stays allowed from the LAN, and from your current SSH client so setup cannot lock you out. `security.firewall_allow` adds CIDRs. |
| `security.docker_daemon_hardening` | on | `/etc/docker/daemon.json` gains `no-new-privileges`, `icc: false`, no userland proxy, `live-restore`, bounded logs (merged into what is there, never replaced). |
| `install_ldap` | on | 389 Directory Server |
| `install_keycloak` | on | Keycloak SSO + Postgres (needed by the web UI) |
| `install_webui` | on | Web UI at `https://mgr.<domain>`: client certificate + Keycloak login + TOTP |

Regardless of the plan, every container runs non-root with all capabilities dropped, `no-new-privileges` and a read-only root filesystem (see [architecture.md](architecture.md#container-hardening)).

Any of these can be set in the vars file and changed later by re-running setup.

### Non-interactive install

```bash
sudo ./setup.sh --file vars.yaml --non-interactive --yes
```

`--non-interactive` never prompts and fails if a required value is missing or invalid; `--yes` accepts the plan.

### Options

| Option | Meaning |
|---|---|
| `--file <path>` | Settings to apply (overrides the existing install's values for the keys it sets) |
| `--non-interactive` | Never prompt |
| `--yes`, `-y` | Accept the plan without asking |
| `--offline` | Never download; packages and images must already be present |
| `--deploy-base <dir>` | Install root (default `/opt`) |
| `--step <name>` | Run only this step (repeatable) |
| `--list` | List the steps |

After setup, `sudo fabricctl doctor` re-runs the end-to-end checks at any time.

### The login kit

With the web UI enabled, setup finishes by creating your first admin and leaving everything your computer needs in `~/fabric-admin/` (of the account that ran `sudo`): the client certificate `<user>.p12` and its password, the initial Keycloak password (you choose a new one at first login), the fabric root CA (`.crt`, and `.cer` for Windows) and a README with the remaining steps: copy the folder to your computer, trust the CA, import the `.p12`, open `https://mgr.<domain>`. Details: [webui.md](webui.md#first-time-setup).

On this host setup already trusts the fabric CA (`/usr/local/share/ca-certificates`), and every service has its certificate from it.

### Steps

| Step | What it does |
|---|---|
| `preflight` | Root, architecture, OS, RAM, cgroup memory controller, conflicting listeners |
| `migrate` | Move a core-template install to fabric in place (no-op otherwise) |
| `host` | Host packages; Docker Engine if missing |
| `docker` | Docker daemon hardening |
| `deploy` | Render and deploy all configuration (nothing started); install `fabricctl` |
| `accounts` | Service users and groups with fixed uids |
| `network` | Docker network `fabric_net`; resolver drop-in unless `use_host_dns` |
| `firewall` | UFW + `DOCKER-USER` rules |
| `pki` | Step-CA init (own root or BYOC), CA certs published and trusted by the host |
| `bootstrap` | Start BIND9 and Step-CA; validate every zone |
| `certs` | Issue/renew service certificates |
| `start` | Start the stack; seed 389-DS; configure Keycloak; fabric-agent + web UI |
| `admin` | First web UI admin: LDAP user in `admins`, forced password change, client `.p12`, root CA and README in `~/fabric-admin` |
| `verify` | DNS, HTTPS chains, LDAPS, role binds, plaintext refused, web UI gates, admin role + client cert, services |

---

## Deployed Structure

The install lives under `/opt` (or `--deploy-base`):

*   `/opt/fabric/`: Contains `config/` (`fabric.yaml` — your settings, `vars.yaml` — the fully rendered variables, `fabric-secrets.yml`, `link-vars.yaml`), the deployed `lib/` and the `fabricctl` entry point (`/usr/local/bin/fabricctl`).
*   `/opt/bind9/`: Core DNS service. Contains `config/` (`named.conf.*`), `data/` (`db.<zone>` zone data and journals), `log/`, `cache/` and `ssl/` (DoT certificate).
*   `/opt/nginx/`: Core reverse proxy. Contains `config/` (`nginx.conf`), `www/` (HTML documentation, scripts, portal assets) and `certs/` (service certificates, `client-ca/` bundle for the web UI).
*   `/opt/stepca/`: Core PKI. Contains `data/` (Internal DB, CA keys in `secrets/`, public CA certs in `certs/`) and `templates/`.
*   `/opt/dirsrv/`: 389 Directory Server. Contains `data/` (389-DS `/data`: config, database, logs, and `tls/` with `server.crt`, `server.key`, `ca/*.crt`) and `seed/` (seed LDIFs + `seed.py`).
*   `/opt/webui/`: Web UI (only when `install_webui`). Contains `docker-compose.yml`, `build/`, `config/webui.json` (`0400`, webui uid), `run/web.sock` (for nginx) and `agent/agent.sock` (created by the host service `fabric-agent`).
*   `/opt/keycloak/`: SSO identity provider. Contains `certs/`.
*   `/opt/postgres/`: Keycloak's database. Contains persistent `data/`.

*Day-2: `fabricctl --apply` renders templates to `/tmp/fabric-render/` and compares them against the live `/opt/` files. A container is only restarted if its configuration changed.*

---

## Upgrading from core-template / OpenLDAP

Running `sudo ./setup.sh` from a fabric checkout on a core-template host migrates it in place (the `migrate` step): paths, units, secrets and the `core-mgr` command (kept as an alias). See [operations.md](operations.md#upgrading-from-core-template).

Installs before 1.5.0 ran `osixia/openldap` in `/opt/openldap`. Setup deploys 389-DS alongside it but does **not** move directory data. Follow [operations.md](operations.md#migrating-from-openldap).

---

## Reinstall / Uninstall

```bash
# Uninstall + setup, keeping config, secrets, the CA and certificates
# (clients keep trusting the CA). NOT kept: the directory (389-DS users,
# groups) and Keycloak's database (TOTP enrolments); setup re-creates the
# first admin with a new login kit.
sudo fabricctl reinstall

# Remove fabric: its containers, images, network, units, service accounts
# and /opt/{fabric,nginx,bind9,stepca,dirsrv,keycloak,postgres,webui}
sudo fabricctl uninstall
```

Both ask for confirmation; `--yes` skips it. From a checkout, `sudo ./setup.sh uninstall` works too. Uninstall only removes fabric's own objects: other containers, networks and Docker settings are left alone.
