# Setup and Installation

fabric is installed as a Debian package, `fabricctl`, on the host it runs on (amd64 or arm64), then set up with `sudo fabricctl setup`. There is no controller machine and no Ansible.

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
- [Rebuilding a host (keep the CA, DNS and TSIG keys)](#rebuilding-a-host-keep-the-ca-dns-and-tsig-keys)
- [Reinstall / Uninstall](#reinstall--uninstall)

---

## Requirements

- Ubuntu 24.04 LTS (the reference; other Debian-family systems get a warning), **amd64 or arm64** (Raspberry Pi 4/5 included)
- 3 GB RAM or more with Keycloak (the default; `preflight` refuses less than about 2.7 GB); 2 GB without it
- cgroup v2 with the memory controller (Raspberry Pi: add `cgroup_enable=memory` to `/boot/firmware/cmdline.txt` if `preflight` asks for it)
- Nothing else listening on the LAN IP's ports 53, 80, 443, 389, 636 (`preflight` warns about these and 853); with DHCP also UDP 67, with 802.1X UDP 1812–1813
- Root (`sudo`) and, unless `--offline`, internet access for apt and the images

The package depends on `python3` (3.10+), `python3-yaml`, `python3-jinja2`, `openssl`, `curl`, `ca-certificates`, `iptables`, `ufw` and `dnsutils` (apt installs them with it) and recommends `python3-pykcs11` and `python3-pykmip` (security keys and KMIP as OpenBao unlock methods). Setup's `host` step installs anything still missing (`gnupg` too) and Docker Engine (`docker-ce`, `containerd.io`, compose and buildx plugins) from Docker's own apt repository if Docker is missing.

## Configure vars

Setup needs five values: `domain`, `hostname`, `host_ip`, `lan_cidr`, `lan_gateway`. Run interactively, it asks for any that are missing and suggests values detected from the default route (and, on a first run, `friendly_name` and the first web UI admin's user name). For everything else, start from the example (in the package at `/usr/share/doc/fabricctl/examples/vars.yaml`; in the repository `fabricctl/examples/vars.yaml`):

```bash
cp /usr/share/doc/fabricctl/examples/vars.yaml custom-vars.yaml
sudo fabricctl setup --file custom-vars.yaml
```

Settings are read in this order, later wins:

1. an existing install's `/opt/fabric/config/vars.yaml` (so re-running setup never loses DNS records added in the web UI or editor)
2. `--file <vars.yaml>` (only the keys it sets). Without `--file`, a fresh install run straight from a git checkout (`python3 fabricctl/lib/fabriclib/cli.py setup`) reads `custom-vars.yaml` at the checkout's root, and so does `install-from-checkout.sh` (it passes it as `--file` when you give none); the package on its own does not.
3. answers to prompts

The merged result is saved as `/opt/fabric/config/fabric.yaml`. Secrets (CA password, TSIG secrets, Directory Manager and per-role LDAP passwords, Keycloak credentials, the web UI's OIDC client secret) are generated on the first run into `/opt/fabric/config/fabric-secrets.yml` (`0600`); the `vault` step then moves them into OpenBao (`fabric/secrets`) and shreds the file. They are kept on every re-run and never appear on a command line. Read one with `sudo fabricctl secrets show <name>`.

Minimum `custom-vars.yaml`:

```yaml
domain: home.arpa               # your internal domain (RFC 8375)
hostname: fabric
host_ip: 10.0.3.53              # this host's LAN IP
lan_cidr: 10.0.0.0/22           # your LAN subnet
lan_gateway: 10.0.0.1

# ── DNS RECORDS ─────────────────────────────────────────────────────────────
# The zone key 'dynamic_zone_var' is the main zone ('domain');
# templates resolve it at render time. Other keys are zone names.
dns:
  dynamic_zone_var:
    zone_authority: true        # emit the "ns" A record pointing to host_ip
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
- [ ] `dns_server` — upstream DNS for the host resolver (only used when `use_host_dns: false`; by default the host's existing resolver is kept)
- [ ] `ca_name`, `cert_country`, `cert_org` — CA subject fields
- [ ] `byoc` / `ca_crt_path` / `ica_crt_path` — bring your own offline root instead of a generated one
- [ ] `dns:` block — A and CNAME records for your hosts
- [ ] `ldap_groups` / `ldap_organizational_units` — directory structure
- [ ] `install_ldap` / `install_keycloak` / `install_webui` — see [the default plan](#the-default-plan) and [webui.md](webui.md)
- [ ] `security.firewall` / `security.firewall_allow` / `security.docker_daemon_hardening`
- [ ] `tsig_keys` — keys for RFC2136 clients (e.g. nginx-proxy-manager); an existing key's `secret` can be given so its clients keep working — see [operations.md](operations.md#tsig-keys-rfc2136-dynamic-updates)
- [ ] `bind_dns_port` — change from `53` only if another DNS server must keep port 53 on `host_ip`
- [ ] `webui_admin_user` — the first web UI admin setup creates (default: the account that ran `sudo`)
- [ ] `webui_hostname` — the web UI's address (default `fabric.<domain>`; any host name)
- [ ] `image_*` — every image is already pinned by digest (`fabricctl/images.lock.yaml`); override only to use a local registry (optional; `fabricctl images update` then leaves it alone unless `--force`)
- [ ] `install_kea` + `dhcp`, `install_freeradius`, `install_fluentbit` + `log_forwarding` — the optional services (off by default; see [the default plan](#the-default-plan) and [operations.md](operations.md#dhcp-optional-kea))

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
sudo apt install ./fabricctl_<version>_all.deb    # installs the tool; changes nothing else
sudo fabricctl setup                              # installs fabric (or: --file vars.yaml)
```

The package is built from the repository with `installers/deb/build-deb.sh` (`dist/fabricctl_<version>_all.deb`, one package for amd64 and arm64), until releases publish it. Installing it only adds `/usr/bin/fabricctl` and the code in `/usr/lib/fabricctl` — it never starts services or touches the network; `fabricctl setup` copies the code to `/opt/fabric` and does the rest. Example settings: `/usr/share/doc/fabricctl/examples/vars.yaml`.

**Upgrade:** install the newer `.deb`, then `sudo fabricctl setup`; until you do, every other command reminds you (`note: the fabricctl package is newer than the running install`). An upgrade never changes the container images a host runs: `fabricctl images update` does (see [operations.md](operations.md#fabricctl-images)). `apt remove fabricctl` removes the tool and leaves the running install alone.

**From a git checkout (development):** `sudo installers/deb/install-from-checkout.sh [setup options]` builds the `.deb` from the checkout (`build-deb.sh`, needs `dpkg-deb`, `git` and `tar`), installs it with apt, then runs `fabricctl setup` with the options given (e.g. `--file custom-vars.yaml --non-interactive --yes`). Running it again upgrades the host to the checkout's current code. Afterwards use `sudo fabricctl …` as usual.

Setup is idempotent: change a setting and run it again; finished steps are quick, and certificates are only re-issued when missing, expiring within 30 days, missing a name or not from this CA.

### The default plan

Every default is the hardened choice. Setup shows the plan and asks **[P]roceed, [A]dvanced, or [Q]uit** (Enter proceeds). Advanced walks each item below and states what relaxing it costs, then asks about the optional services, and shows the plan again. `--yes` or `--non-interactive` proceeds without asking.

| Setting | Default | Relaxing it means |
|---|---|---|
| `security.firewall` | on | UFW default-deny; fabric's ports from the LAN only, also enforced for Docker-published ports (`DOCKER-USER`, re-applied at boot by `fabric-firewall.service`). SSH stays allowed from the LAN, and from your current SSH client so setup cannot lock you out. `security.firewall_allow` adds CIDRs. |
| `security.docker_daemon_hardening` | on | `/etc/docker/daemon.json` gains `no-new-privileges`, `icc: false`, no userland proxy, `live-restore`, bounded logs (merged into what is there, never replaced). |
| `install_ldap` | on | 389 Directory Server |
| `install_keycloak` | on | Keycloak SSO + Postgres (needed by the web UI) |
| `install_webui` | on | Web UI at `https://fabric.<domain>` (`webui_hostname`): client certificate + Keycloak login + TOTP. Forced off when Keycloak is off |

Optional services, off by default (Advanced asks about each; or set them in the vars file):

| Setting | Advanced asks | See |
|---|---|---|
| `install_kea` + `dhcp` | DHCP on this LAN with Kea: interface, subnet, address pool (default: the top quarter of the subnet) and router, suggested from the default route. Switch off your router's DHCP first | [operations.md](operations.md#dhcp-optional-kea) |
| `install_freeradius` | 802.1X with FreeRADIUS; refused without 389-DS (`install_ldap`). Switches are added afterwards with `fabricctl radius add-client` | [operations.md](operations.md#8021x-optional-freeradius) |
| `install_fluentbit` + `log_forwarding` | Forward all logs with Fluent Bit: a syslog server `host[:port]` over TLS (port 6514 by default) and/or an Elasticsearch/OpenSearch URL and user; its password afterwards with `fabricctl logs set-password elastic` | [operations.md](operations.md#log-forwarding-optional-fluent-bit) |

Regardless of the plan, every container runs non-root with all capabilities dropped, `no-new-privileges` and a read-only root filesystem (see [architecture.md](architecture.md#container-hardening)).

Any of these can be set in the vars file and changed later by re-running setup.

### Non-interactive install

```bash
sudo fabricctl setup --file vars.yaml --non-interactive --yes
```

`--non-interactive` never prompts and fails if a required value is missing or invalid (the first web UI admin then defaults to the account that ran `sudo`, or `fabricadmin`); `--yes` accepts the plan.

### Options

| Option | Meaning |
|---|---|
| `--file <path>` | Settings to apply (overrides the existing install's values for the keys it sets) |
| `--non-interactive` | Never prompt |
| `--yes`, `-y` | Accept the plan without asking |
| `--offline` | Never download; packages and images must already be present |
| `--deploy-base <dir>` | Install root (default `/opt`) |
| `--step <name>` | Run only this step (repeatable); the plan is not shown. An unknown name is refused |
| `--list` | List the steps |
| `--join [@FILE \| -]` | Join an existing fabric as a new site (a fresh install only). The invitation is pasted at a hidden prompt, read from `@FILE` or from stdin (`-`); never on the command line, which every user on the host can read: see [Joining an existing fabric](#joining-an-existing-fabric-a-new-site) |

After setup, `sudo fabricctl doctor` re-runs the end-to-end checks at any time. When a step fails, setup stops there with the reason (exit 1; some errors show a Python traceback instead): fix it and run setup again. Interrupted, it exits 130.

### Joining an existing fabric (a new site)

On the fabric this site joins (its upstream; design [federation.md](design/federation.md)):

```bash
sudo fabricctl federation enable          # once: the endpoint sites join through
sudo fabricctl federation invite branch1  # one-time invitation, good for one hour
```

On the new host, a fresh install:

```bash
sudo fabricctl setup --join            # paste the invitation at the (hidden) prompt
```

The site's name comes from the invitation; its domain defaults to `<site>.<organisation domain>`
(set `domain` in a `--file` to choose another). Its certificate authority is an intermediate signed by
the organisation's root (the key is made on the site and never leaves it), and it shares the
organisation's directory suffix. Directory and DNS links between the sites follow in later milestones.

### CA certificates for your devices

`https://certs.<domain>/` lists the root and intermediate CA certificates with their fingerprints, per-system instructions and every format:

| File | Format | For |
|---|---|---|
| `root-ca.cer`, `intermediate-ca.cer` | DER | Windows |
| `root-ca.crt`, `intermediate-ca.crt` | PEM | Linux, macOS, iOS, Android |
| `root-ca.pem`, `intermediate-ca.pem` | PEM, shown as text | copy & paste into network devices |
| `root-ca.der`, `intermediate-ca.der` | DER | devices that want a binary certificate |
| `ca-chain.p7b` | PKCS#7 (root + intermediate) | Windows, Java, many appliances |
| `ca-chain.pem` | PEM bundle (intermediate, then root) | devices that import a chain |
| `ca-certs.json` | subjects, validity, SHA-256/SHA-1 fingerprints | scripts |

`https://ca.<domain>/` is Step-CA's API (ACME: `https://ca.<domain>/acme/acme/directory`); opened in a browser it redirects to the certificate page. The files are re-published on every setup run.

### The login kit

With the web UI enabled, setup finishes by creating your first admin and leaving everything your computer needs in `~/fabric-admin/` (of the account that ran `sudo`): the client certificate `<user>.p12` and its password, the initial Keycloak password (you choose a new one at first login), the fabric root CA (`.crt`, and `.cer` for Windows) and a README with the remaining steps: copy the folder to your computer, trust the CA, import the `.p12`, open `https://fabric.<domain>`. Details: [webui.md](webui.md#first-time-setup).

On this host setup already trusts the fabric CA (`/usr/local/share/ca-certificates`), and every service has its certificate from it.

### Running it: systemd

Every service is its own systemd unit, all grouped under **`fabric.target`**, which is enabled at boot:

```bash
sudo fabricctl status            # the target, every unit and its container health
sudo fabricctl stop              # = systemctl stop fabric.target (every fabric service)
sudo fabricctl start             # returns once every service is up and healthy
sudo fabricctl restart
systemctl status fabric-web      # one service
```

Units: `bind9`, `stepca`, `nginx`, `ldap`, `postgres`, `keycloak`, `openbao`, `fabric-agent`, `fabric-web`; with the optional services `kea`, `freeradius`, `fluentbit`. `fabric-firewall` re-applies the firewall rules at boot. `openbao` starts only when an unlock method is present (see [operations.md](operations.md#openbao-secrets)).

### Steps

| Step | What it does |
|---|---|
| `preflight` | Root, architecture, RAM, cgroup memory controller (refused if wrong); OS and other programs on fabric's ports (warnings). Changes nothing |
| `host` | Host packages; Docker Engine with compose and buildx if missing (never downloads with `--offline`) |
| `docker` | Docker daemon hardening |
| `join` | Only with `--join`: join the upstream — this site's CA key and request (the key stays here), the upstream's root pinned by the invitation's fingerprint, the join over TLS verified against it, the signed intermediate checked and set up as this install's CA (bring-your-own path), the organisation's settings. A re-run reuses what was staged |
| `deploy` | Save the settings to `fabric.yaml`; render and deploy all configuration (nothing started); the `fabricctl` command (the package's, or `/usr/local/bin/fabricctl` when run from a checkout) |
| `accounts` | Service users and groups with fixed uids |
| `network` | Docker network `fabric_net`; resolver drop-in unless `use_host_dns` |
| `firewall` | UFW + `DOCKER-USER` rules; refuses if your SSH client would be locked out |
| `pki` | Step-CA init (own root or BYOC), CA certs published and trusted by the host |
| `bootstrap` | Start BIND9 and Step-CA; validate every zone |
| `certs` | Issue/renew service certificates and `extra_certs` |
| `start` | Start the stack; seed 389-DS and the default device roles; configure Keycloak; the optional services; fabric-agent + web UI |
| `vault` | OpenBao: vault key and unlock methods, first-time init (recovery keys to `~/fabric-admin`), configuration, import fabric's secrets and shred the file |
| `admin` | First web UI admin: LDAP user in `admins`, forced password change, client `.p12`, root CA and README in `~/fabric-admin` |
| `verify` | DNS, HTTPS chains, the CA page and host trust, LDAPS, role binds, plaintext refused, web UI gates, admin role + client cert, OpenBao (unsealed, unlock methods, KV mounts, `vault.<domain>`), services |

---

## Deployed Structure

The install lives under `/opt` (or `--deploy-base`):

*   `/opt/fabric/`: Contains `config/` (`fabric.yaml` — your settings, `vars.yaml` — the fully rendered variables, `secrets.openbao` — the marker saying fabric's secrets are in OpenBao, `link-vars.yaml`), `archive/` (audit log, earlier vars files), the deployed `lib/` and `jinja/`, `VERSION` and `BUILD`. The command is the package's `/usr/bin/fabricctl` (or `/usr/local/bin/fabricctl`, written by setup run from a checkout).
*   `/opt/openbao/`: OpenBao. `config/`, `data/` (Raft storage), `logs/` (audit log), `certs/`. Its vault key and unlock methods are in `/etc/fabric/openbao/` (root only).
*   `/opt/kea/`, `/opt/freeradius/`, `/opt/fluentbit/`: the optional services, when installed.
*   `/opt/bind9/`: Core DNS service. Contains `config/` (`named.conf.*`), `data/` (`db.<zone>` zone data and journals), `log/`, `cache/` and `ssl/` (DoT certificate).
*   `/opt/nginx/`: Core reverse proxy. Contains `config/` (`nginx.conf`), `www/` (HTML documentation, scripts, portal assets) and `certs/` (service certificates, `client-ca/` bundle for the web UI).
*   `/opt/stepca/`: Core PKI. Contains `data/` (Internal DB, CA keys in `secrets/`, public CA certs in `certs/`) and `templates/`.
*   `/opt/dirsrv/`: 389 Directory Server. Contains `data/` (389-DS `/data`: config, database, logs, and `tls/` with `server.crt`, `server.key`, `ca/*.crt`) and `seed/` (seed LDIFs + `seed.py`).
*   `/opt/webui/`: Web UI (only when `install_webui`). Contains `docker-compose.yml`, `build/`, `config/webui.json` (`0400`, webui uid), `run/web.sock` (for nginx) and `agent/agent.sock` (created by the host service `fabric-agent`).
*   `/opt/keycloak/`: SSO identity provider. Contains `certs/`.
*   `/opt/postgres/`: Keycloak's database. Contains persistent `data/`.

*Day-2: `fabricctl --apply` renders templates to `/tmp/fabric-render/` and compares them against the live `/opt/` files. A container is only restarted if its configuration changed.*

---

## Rebuilding a host (keep the CA, DNS and TSIG keys)

fabric has no in-place upgrade from pre-fabric (core-template) installs: rebuild the host and carry over what clients depend on.

- **DNS records and zone:** copy the `domain` and the `dns:` block into your vars file.
- **TSIG keys** (RFC2136 clients such as nginx-proxy-manager): add each key to `tsig_keys` with its existing `secret` — see [operations.md](operations.md#tsig-keys-rfc2136-dynamic-updates). Clients keep their configuration.
- **Root CA:** bring your root and intermediate (with its key) as [BYOC](#generate-pki-optional-before-install), so every client that trusts the old root trusts the new host. Step-CA reads the intermediate key with `ca_password` from `/opt/fabric/config/fabric-secrets.yml`: if your key is encrypted, create that file (`0600`, in a new `/opt/fabric/config/`) with `ca_password: <the old CA password>` before the **first** setup (it is then moved into OpenBao with the others).

LDAP and Keycloak start empty; setup creates the first admin.

To move a fabric install (not a pre-fabric one) to a new host with everything — directory, Keycloak and OpenBao included — use `fabricctl uninstall --export` and `fabricctl restore` instead (below).

---

## Reinstall / Uninstall

```bash
# Uninstall + setup, keeping config, secrets, the CA, certificates and
# OpenBao (its data and vault key) — clients keep trusting the CA. NOT kept:
# the directory (389-DS users, groups, devices) and Keycloak's database
# (TOTP enrolments); setup re-creates the first admin with a new login kit.
# Asks first (--yes: don't); other options go to setup.
sudo fabricctl reinstall

# Remove fabric. It asks first: export all of fabric's data to a folder
# you choose? remove the fabricctl package too (apt purge)?
sudo fabricctl uninstall

# Unattended: the export choice must be explicit
sudo fabricctl uninstall --yes --export /root/fabric-export --purge-package
sudo fabricctl uninstall --yes --no-export

# Bring it back from an export (the same host or a new one, package installed)
sudo fabricctl restore /root/fabric-export
```

`fabricctl reinstall` first copies what it keeps to
`/root/fabric-reinstall-<time>/` (root only; with fabric's secrets in plain
text, the CA keys and the vault key). The folder is left there after the
reinstall: delete it once fabric works again.

`fabricctl restore` asks first (`--yes`: don't), puts the export back in
place (owners and modes kept) and runs setup on it unattended
(`--yes --non-interactive`): the same CA (clients keep trusting it), the same
directory users and devices, Keycloak with its TOTP enrolments, DNS with
its TSIG keys, and OpenBao with its data — its vault key comes back with
it, so the key-file unlock method works at once (a USB stick or security
key must be plugged in). It refuses while fabric is installed and any
folder that is not an export. The export's plaintext copy of fabric's
secrets goes back into OpenBao and is shredded.

`fabricctl uninstall` is the recommended way: the export goes only where you
say, so nothing is left in `/var` or anywhere else. Every question is asked
before anything is touched: export first (default yes, to
`~/fabric-export-<time>` of the account that ran `sudo`)? remove the package
too (default no)? then type `yes`. The export folder must be an absolute
path, new or empty, and not inside anything the uninstall deletes; otherwise
it is refused and nothing changes. With `--yes` the export choice must be
given (`--export DIR` or `--no-export`).

It removes every service and `fabric.target`, the containers, the
`fabric_net` network, fabric's locally built images, fabric's `DOCKER-USER`
rules, the `/opt/<service>` folders (and TSIG credential folders), the vault
key and unlock-method files, the USB kill-switch rule, the service accounts,
the CA from the host trust store, the resolver drop-in and a checkout-era
`/usr/local/bin/fabricctl`. Docker, downloaded images and other containers
are not touched; ufw stays enabled.

| Command | fabric install | Package | Export |
|---|---|---|---|
| `sudo fabricctl uninstall` | removed | removed if you say so | to the folder you choose, if you want one |
| `sudo apt remove fabricctl` | **kept, still running** | removed | — |
| `sudo apt purge fabricctl` | removed | removed | always, to `/var/backups/fabric/fabric-export-<time>/` (apt cannot ask) |

The export (root only, with a README) holds the config, fabric's secrets in
plain text, the whole CA, the directory (users, devices, roles), Keycloak's
database, every certificate and OpenBao's data with its vault key. It was
copied while the stack was stopped, so the databases are consistent.
Whoever has it has your CA and your vault: move it offline, delete it when
you no longer need it.
