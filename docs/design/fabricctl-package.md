# Design: `fabricctl` as an apt package (replacing Ansible), Kea DHCP, 802.1X

Status: **proposal — for decision**. Nothing here is implemented yet.

## 1. Goal

Installing fabric today means cloning the repo on a controller, installing
Ansible and running 12 playbooks (~3,000 lines) against the target over SSH.
The goal:

```bash
sudo apt install fabricctl        # one package, one command
sudo fabricctl init               # interactive, or: fabricctl init --config fabric.yaml
```

Everything `setup.sh` + Ansible does today (preconditioning, rendering,
PKI bootstrap, containers, checks) happens locally on the host, driven by
`fabricctl`. Day-2 operations stay the same command (`fabricctl apply`,
`fabricctl dns ...`) and the web UI.

The package and the command share one name. Plain `fabric` is taken
(Python Fabric is packaged as `fabric` in Debian and Ubuntu); `fabricctl` is
free in Debian trixie and Ubuntu 24.04.

Scope beyond the installer: add **Kea DHCP** and **802.1X (FreeRADIUS)**, and
grow the web UI to manage every service.

## 1a. Two products: fabricctl and Fabric

| | **fabricctl** — the control | **Fabric** — the control-plane UI |
|---|---|---|
| What | Native apt package on the host | Web app in its own unprivileged container |
| Role | The integration point: installs, configures, updates and secures the whole stack — containers, host firewall, Docker daemon, image updates, OpenBao seals and hardware tokens | Configuration and control plane in the browser: status, DNS/DHCP/users/secrets, triggering operations. Holds no power of its own |
| Stands alone? | **Yes** — everything is possible from the CLI | No — every action is a request to fabricctl's daemon |
| Artifact | `fabricctl` .deb: `fabricctl` CLI + `fabricd` daemon + systemd timers | `fabric` container image, installed, pinned (via the channel) and updated by fabricctl |

One repo (`archdukejim/fabric`) builds and tests both; each fabricctl
version declares the Fabric image it expects.

**Privilege model (decided):**

- **`fabricd`** — root, sandboxed systemd service; the *only* component that
  touches Docker, nftables, systemd, udev and OpenBao seal configuration.
  It exposes a fixed, validated operation API (today's `fabric-agent`,
  generalised) — never "run this command".
- **`fabricctl` CLI** runs as the invoking user and talks to `fabricd` over
  a socket restricted to the **`fabric-admins`** group. Membership grants
  fabric's operations, not a root shell. **Nobody is added to the `docker`
  group** (that group is root-equivalent).
- **Fabric UI** reaches `fabricd` over its own socket, identified by its
  container uid (SO_PEERCRED); operations are further filtered by the
  user's Keycloak role.
- Every operation is audited with the real actor: Unix user for the CLI,
  Keycloak user for the UI.

## 1b. Setup: secure by default, fully scriptable

`sudo fabricctl setup` (first run, or `--reconfigure` later):

1. Preflight (architecture, RAM, cgroup memory controller, Docker, ports).
2. Shows **the full list of changes it will make by default** — every one a
   hardened choice — then offers **Proceed** or **Advanced**.
3. **Advanced** walks the same list item by item, allowing each to be kept
   or relaxed, with the consequence of relaxing it stated inline.

Default plan (each item is a setting under `security:` / `updates:` /
`vault:` in `fabric.yaml`):

| Item | Default | Can relax to |
|---|---|---|
| Host firewall (nftables) | On: only fabric's service ports inbound; management (443/`mgr`, SSH) from `lan_cidr` only | Off, or custom allow-lists |
| Container hardening | On: non-root, `cap_drop: ALL`, `no-new-privileges`, read-only root where possible | Per-service exceptions |
| Docker daemon | Hardened `daemon.json` (`no-new-privileges`, `icc: false`, `userland-proxy: false`, `live-restore`) | Stock daemon config |
| userns-remap | **On** (container root → unprivileged host uid; fabricctl shifts bind-mount ownership) | Off |
| Rootless Docker | Off | On, with stated limits: Kea DHCP unavailable, DNS/RADIUS source-IP ACLs need the slower slirp4netns/pasta port driver |
| OpenBao unseal | Local key file | USB kill switch, Thales k160 (KMIP), PKCS#11 token, or manual Shamir |
| Image updates | On: signed stable channel, weekly, health-checked with rollback | Off, candidate channel, or offline-only |
| Web UI access | mTLS + Keycloak OIDC + TOTP | TOTP optional |

Non-interactive: `sudo fabricctl setup --file ./vars.yaml` takes every
answer (including all of the above) from the file; the walkthrough only
prompts for missing or invalid values. `--non-interactive` never prompts
and fails on anything missing — for automation and re-provisioning.

Every setting can be changed later (`fabricctl security …`,
`fabricctl vault seal-…`, `fabricctl updates …`, or editing `fabric.yaml` +
`fabricctl apply`). `fabricctl status` and the Fabric dashboard show a
**security posture** summary that lists every relaxed default as a warning.

## 2. What exists to build on

| Today | Reuse |
|---|---|
| `fabric/lib/deploy.py` — native render + deploy + selective reload (what `fabricctl apply` runs) | Becomes the core of the installer; already replaces playbooks 01 and 04 for day-2 changes |
| `fabric/lib/webui/` (container app), `fabric/lib/agent/` (fabric-agent), `keycloak_bootstrap.py`, `dirsrv.sh`, `ldap_migrate.*` | Ship as-is inside the package |
| `fabric/jinja/**` templates | Ship as-is (package data) |
| Playbooks 02, 03, 05–10 | **Port** to Python modules (see §4) |
| `package.sh` offline bundles | Becomes an image bundle next to the `.deb` |

Only the "first install" half of the Ansible code needs porting; the
day-2 half is already native.

## 3. Package design

```
fabricctl_<ver>_<arch>.deb
  /usr/bin/fabricctl                      entry point (Python)
  /usr/lib/fabricctl/                     fabric/lib (deploy, agent, webui build context, seeders, bootstrap)
  /usr/share/fabricctl/templates/         fabric/jinja
  /usr/share/fabricctl/images/            (optional, "fabricctl-images" package) docker save tarballs
  /lib/systemd/system/fabric-agent.service shipped static, config in /etc
  /lib/systemd/system/webui.service       compose wrapper for the webui container
  /etc/fabric/                            conffiles: fabric.yaml (vars), link-vars.yaml
  /var/lib/fabric/                        secrets, rendered vars, archive/audit
```

- **Depends:** `python3 (>= 3.11)`, `python3-yaml`, `python3-jinja2`,
  `docker.io | docker-ce`, `docker-compose-v2 | docker-compose-plugin`,
  `openssl`, `curl`. All from the distro — no pip, no venv.
- **Architectures:** `all` (pure Python) — one package for amd64 and arm64
  (Raspberry Pi). Images are per-arch and pulled/built at `init`.
- **Maintainer scripts** stay minimal (create `fabric` system group,
  directories). `postinst` never starts services or touches the network —
  `fabricctl init` does the real work, so `apt install` is always safe and
  reversible.
- **Config location:** move from `/opt/fabric/config` to `/etc/fabric`
  (config) and `/var/lib/fabric` (state) per FHS; service data stays in
  `/opt/<service>` (or becomes `/var/lib/fabric/<service>`, decision D3).
  `fabricctl` migrates `/opt/fabric` on first run (like `00b-migrate-from-core`).
- **Distribution:** a signed apt repository published from GitHub Actions to
  GitHub Pages (`aptly`/`reprepro`, GPG key in repo secrets). Users add one
  `sources.list.d` entry + keyring. Releases also attach the `.deb` for
  manual `apt install ./fabricctl_*.deb`.
- **Offline installs:** `fabricctl-images_<ver>_<arch>.deb` (or a tarball)
  carries `docker save` output; `fabricctl init --offline` loads it.

### Language

| Option | Pros | Cons |
|---|---|---|
| **Python in the .deb (recommended)** | Reuses deploy.py, webui, bootstrap, seeders (~70% of the code); Debian-native deps; `Architecture: all` | Python startup (~150 ms); distro Python version floor |
| Go static binary | Single file, no runtime deps | Full rewrite incl. web UI and Keycloak/LDAP logic; templates must move to Go `text/template` or keep a Jinja dependency |

## 4. Porting the playbooks

Each playbook becomes an idempotent, individually re-runnable step
(`fabricctl init --step pki`), with the same checks as today:

| Playbook | `fabricctl` step | Notes |
|---|---|---|
| 00 controller check | *(gone)* | No controller any more |
| 00b migrate-from-core | `migrate` | Also migrates `/opt/fabric` → `/etc` + `/var/lib` |
| 01 gen vars + render | `render` | Already in deploy.py |
| 02 system conditioning | `precondition` | Packages come from `Depends:`; sysctl, free port 53 from systemd-resolved, time sync check |
| 03 service accounts | `accounts` | `systemd-sysusers` snippet shipped in the package |
| 04 file structure | `render` / `deploy` | Already in deploy.py |
| 05 network | `network` | Resolver drop-in, `fabric_net` |
| 06 configure Step-CA | `pki` | Largest port: CA init, BYOC import |
| 07 bootstrap containers | `pki` | |
| 08 mint service certs | `certs` | Logic already duplicated in services.sh; consolidate |
| 09 start + configure | `start` | dirsrv seed + keycloak_bootstrap already native |
| 10 checks | `check` | Also exposed as `fabricctl doctor` and in the web UI |

**Remote install without Ansible:**

```bash
ssh admin@pi 'sudo apt install -y fabricctl && sudo fabricctl init --config -' < fabric.yaml
```

`setup.sh` stays for one release as a thin wrapper that does exactly that,
then is removed along with `fabric/playbooks/`.

## 5. Kea DHCP

- **Kea 3.0 LTS** (ISC). As of Kea 3.0 almost all hook libraries are open
  source (MPL 2.0) — including host/subnet commands, lease commands, HA; only
  RBAC and the Configuration Backend remain commercial. The DHCP daemons now
  serve their API directly over HTTPS with client-cert auth; the Control
  Agent is deprecated and not needed.
- **Runs in a container with `network_mode: host`** (DHCP needs broadcast on
  the LAN interface) — or natively from the distro/ISC Cloudsmith packages
  (decision D4). Leases in **memfile** (no DB dependency) or Postgres
  (already deployed for Keycloak) for HA/web-UI queries.
- **Source of truth:** `fabric.yaml` gains `dhcp:` (subnets, pools, options,
  reservations). Rendered to `kea-dhcp4.conf`; applied with `config-set` +
  `config-write` via the API — no restart, leases untouched.
- **DDNS:** `kea-dhcp-ddns` → BIND9 with a dedicated TSIG key, auto-created
  in `tsig_keys` with `update-policy` scoped to A/AAAA/PTR/DHCID. Reuses the
  dynamic-zone handling fixed in 1.5.0.
- **Reservations ↔ DNS:** a reservation with a hostname produces the A/PTR
  record, so one entry in the UI does both.
- **HA (optional):** Kea HA hook, hot-standby between two fabric nodes.
- **API security:** HTTPS listener on `127.0.0.1`/`fabric_net` only, mTLS
  with a Step-CA client cert held by `fabricctl`/webui.

## 6. 802.1X (FreeRADIUS)

- **FreeRADIUS 3.2** container; RADIUS clients = switches/APs listed in
  `fabric.yaml` (`radius_clients:` with per-client shared secrets in
  `fabric-secrets.yml`). RadSec (RADIUS over TLS, Step-CA certs) where the
  switch supports it.
- **Primary method: EAP-TLS** with device/user certificates from Step-CA.
  - Enrolment: Step-CA **SCEP provisioner** for MDM/network gear, ACME for
    Linux hosts, `fabricctl --client-cert` / web UI for manual issuance.
  - SCEP requires an RSA intermediate — fabric's default
    (`cert_intermediate_key_type: rsa`) already satisfies this.
  - Revocation: short-lived certs (Step-CA passive revocation) plus an
    OCSP/CRL check in FreeRADIUS.
- **Username/password fallback: EAP-TTLS/PAP against 389-DS.** Not
  PEAP-MSCHAPv2: MSCHAPv2 needs NT hashes, which 389-DS does not store
  (and should not).
- **MAB** (MAC auth bypass) for printers/IoT, keyed off Kea reservations —
  a device reserved in DHCP can be admitted to its VLAN by MAC.
- **Dynamic VLANs:** LDAP group → `Tunnel-Private-Group-Id` mapping
  (`vlans:` in `fabric.yaml`), so group membership in 389-DS/Keycloak
  decides the network segment. CoA/Disconnect for quarantine from the UI.

## 7. Web UI as the single pane

Same security model (mTLS + Keycloak OIDC + TOTP + CSRF) and the same
privilege split: the UI runs in its own unprivileged container (`webui`, no
caps, read-only, no Docker socket) and reaches the host only through
`fabric-agent` — a root host service with a fixed, validated, audited JSON
API on a unix socket (SO_PEERCRED-checked). Each new section is a new agent
endpoint over `fabricctl` actions, so CLI and UI never diverge:

- **DHCP:** subnets, live leases (lease API), reservations (creates DNS).
- **802.1X:** RADIUS clients, recent auth log, device certs (issue/revoke),
  VLAN mappings, CoA.
- **PKI:** issued certs, expiry, revoke, SCEP/ACME provisioners.
- **Directory:** users/groups in 389-DS (via a least-privilege role account,
  not Directory Manager).
- **Health:** `fabricctl doctor` output, service status, versions, updates.

Role split (Keycloak realm roles): `fabric-admin` (everything),
`fabric-operator` (DNS/DHCP/leases, no PKI/directory), `fabric-auditor`
(read-only).

## 7a. Targets and hardening

- **Architectures:** everything runs on **arm64 and amd64**. Every upstream
  image used publishes both (verified 2026-09-27: nginx, ubuntu/bind9,
  step-ca, keycloak, postgres, debian, registry, osixia/openldap for the
  migration). Locally built images (`dirsrv`, `webui`) start from
  `debian:trixie-slim` and build natively on either.
- **Reference hardware:** Raspberry Pi, **4 GB**, Ubuntu Server 24.04 LTS
  (arm64). Development/testing on amd64. Memory limits at 4 GB total ≈ 2.3 GB
  (Keycloak 1.2 GB is the bulk), leaving ~1 GB for Kea, FreeRADIUS, the
  registry and the updater.
- **Preflight** (refuses to install): architecture is arm64/amd64; ≥ 3 GB RAM
  with Keycloak; the cgroup v2 **memory** controller is enabled (otherwise
  Docker silently ignores every limit — a Pi-specific trap); Docker engine
  and compose v2 present.
- **Container hardening:** every container non-root, `cap_drop: ALL` plus
  only the capabilities it needs, `no-new-privileges`, read-only root where
  the image allows. Where an upstream image needs its permissions reworked,
  a thin local build layer does it — always `FROM` a pinned digest (§7b), so
  an upstream push can never change what gets built.
- **Docker daemon:** `no-new-privileges` by default, `icc: false`,
  `userland-proxy: false`, `live-restore: true`. The installer **asks**
  `userns-remap` is **on by default** (container root → unprivileged host
  uid); setup can turn it off (§1b). Rootless Docker is an opt-in relaxation
  with stated limits: it hides client source IPs unless the slower
  slirp4netns/pasta port driver is used (BIND/RADIUS ACLs), has no real host
  networking (no Kea DHCP) and needs a system-wide low-port sysctl.
- **Line endings:** `.gitattributes` forces LF so a Windows checkout can't
  ship CRLF scripts or Dockerfiles to the Pi.

## 7b. Image channels (tested versions, decoupled from releases)

The tested set of image versions is published **separately from fabric
releases**, so a Pi running an older fabric still gets newly tested images.

**The channel file** — `stable.json` (and `candidate.json`), served from
GitHub Pages (`https://archdukejim.github.io/fabric/channels/stable.json`):

```json
{
  "channel": "stable",
  "serial": 42,
  "issued": "2026-10-04T03:00:00Z",
  "expires": "2026-11-03T03:00:00Z",
  "requires_fabric": ">=1.5.0",
  "images": {
    "keycloak": {"ref": "keycloak/keycloak:26.7.4",
                 "digest": "sha256:…", "platforms": ["linux/amd64", "linux/arm64"]},
    "debian":   {"ref": "debian:trixie-slim", "digest": "sha256:…"}
  }
}
```

plus `stable.json.sig`, an **Ed25519 signature**. The public key ships inside
fabric; verification uses the `openssl` already on every host (no new
dependency). Digests are the multi-arch index digest, so one entry covers
both architectures. `debian` pins the base of the locally built images.

**Producing it (automated, GitHub Actions):**

1. Scheduled job (weekly, and on demand) proposes candidate versions within
   the allowed policy (e.g. new patch releases of pinned minors), resolves
   digests.
2. Runs the full real-container suites (web UI, 389-DS, Keycloak, DNS, and
   Kea/RADIUS later) on **amd64 and arm64** runners with the candidate set.
3. All green → signed `candidate.json` is published; after a soak period
   with no regressions it is promoted to `stable.json` with a higher serial.
   The signing key lives only in a protected GitHub environment.

**Consuming it (`fabric-update.timer`, optional, asked at install):**

1. Fetch channel + signature (TLS); verify signature, `serial` greater than
   the installed one (no rollback/freeze attacks), not expired,
   `requires_fabric` satisfied. Any failure → change nothing, report in the
   web UI and audit log.
2. Pull each changed image **by digest** and push it into the local registry.
3. Roll out one service at a time through its systemd unit; wait for the
   healthcheck; on failure restore the previous digest and stop.
4. Rebuild local images (`dirsrv`, `webui`) on the pinned `debian` digest.

**Offline (air-gapped):** the same signed file travels by hand.

- On any online machine: `fabricctl images export --channel stable
  --arch arm64 -o fabric-images-42-arm64.tar` → signed channel file + image
  tarballs, verified by digest at export.
- On the offline host: `fabricctl images import fabric-images-42-arm64.tar`
  verifies signature, serial, expiry policy and every digest, loads the
  images into the local registry, then runs the same rollout as above.
- Several offline hosts can instead follow a **local mirror**: point
  `image_channel_url` at an internal HTTPS path (e.g. served by fabric's own
  nginx) where an admin drops a verified channel file; the updater treats it
  exactly like GitHub Pages. For long-offline sites, `expires` can be
  checked as a warning instead of a hard stop (`image_channel_offline: true`).

**Local registry:** `registry:3` on `fabric_net`, TLS from Step-CA
(`registry.<domain>`). Every compose file pulls from it, online or offline,
so the local registry is the single gate: nothing runs that did not pass
signature and digest checks. No Watchtower and no Docker-socket container;
the updater is part of `fabricctl` and uses the same systemd units as
everything else.

## 7c. Secrets: OpenBao

**OpenBao** (MPL-2.0, Linux Foundation fork of Vault; Vault-compatible API,
CLI and clients) rather than HashiCorp Vault, whose BSL licence is not open
source. Multi-arch images; ~150 MB at 4 GB (fits the §7a budget).

- **Deployment:** container `openbao` on `fabric_net`, integrated **Raft**
  storage in `/opt/openbao/data`, TLS listener with a Step-CA certificate;
  published as `https://vault.<domain>` through nginx (CNAME `vault`). Same
  hardening as every container (§7a); image pinned via the channel (§7b).
- **Unseal (decided: auto-unseal from a local key file):** the unseal key
  lives in `/etc/fabric/openbao/unseal.key` (root, 0400) — optionally on a
  removable USB stick mounted at boot. OpenBao unseals itself on start, so a
  power cut does not need a human. **Trade-off, stated in the installer:**
  whoever holds the SD card (or USB stick) holds the vault. Recovery shares
  and the initial root token are shown once at `init`; the root token is
  revoked after bootstrap.
- **Seal modes and commands** (all native to OpenBao ≥ 2.3; switching modes
  is an OpenBao *seal migration*: the old seal is kept with
  `disabled = "true"`, OpenBao restarts, and `bao operator unseal -migrate`
  runs with the **recovery keys** shown at `init` — `fabricctl` walks
  through it and refuses to start without them):

  | Mode | Command | Unseal source | At boot |
  |---|---|---|---|
  | Local file (default) | — | `static` seal, key in `/etc/fabric/openbao/unseal.key` | Automatic |
  | **USB kill switch** | `fabricctl vault key-to-usb /dev/sdX [--backup /dev/sdY]` | `static` seal, key only on a USB stick (label `FABRIC-KEY`) | Automatic if the stick is present, sealed if not |
  | **Thales CipherTrust k160** (or any KMIP server) | `fabricctl vault seal-kmip --endpoint k160.lan:5696 --ca … --client-cert … --client-key … --key-id …` | `kmip` seal — the root key is wrapped by a key that never leaves the k160 (FIPS 140-2 token) | Automatic while the k160 is reachable and authorises this client |
  | PKCS#11 token (SafeNet eToken, YubiHSM 2, Nitrokey HSM) | `fabricctl vault seal-pkcs11 --lib … --token-label … --key-label …` | `pkcs11` seal via the vendor library (built into a thin local image layer) | Automatic while the token is plugged in |

  Every mode can move to every other (`fabricctl vault seal-usb`,
  `seal-local`, `seal-kmip`, `seal-pkcs11`).

- **USB kill switch details:**
  - `key-to-usb` writes a fresh 32-byte key (with key id + checksum) to the
    stick, verifies it, rotates OpenBao onto it (static seal supports
    `previous_key` → `current_key` rotation), then **shreds** the on-disk
    copy. `--backup` writes the same key to a second stick for the safe.
  - A udev rule + systemd units: **insert** → mount read-only at
    `/run/fabric/key` (tmpfs mount point, never under `/opt`) and start/
    unseal OpenBao; **remove** → `bao operator seal` immediately (the root
    key is wiped from memory) and unmount. Pulling the stick is the kill
    switch; the data on the SD card stays encrypted and useless without it.
  - The container mounts the key directory with `rslave` propagation, so a
    stick inserted after start is visible without recreating the container.
  - Limits, stated in the command's output: someone holding both the Pi and
    the stick can unseal; a stick left in the Pi is the same as the local
    file mode.

- **Thales CipherTrust k160 details:**
  - The k160 is a network appliance (KMIP on TCP 5696, mutual TLS).
    `seal-kmip` needs: endpoint, the k160's CA, a KMIP client certificate
    registered on the k160 (the command can issue one from fabric's Step-CA
    for upload, or use one issued by the k160), and the id of an AES-256
    key with encrypt/decrypt usage (or `--create-key`).
  - It test-wraps and unwraps a value through the k160 before migrating, so
    a misconfiguration never leaves OpenBao unsealable.
  - Revoking the client on the k160 is the "official" kill switch: at the
    next restart OpenBao stays sealed. Core services keep running (below).

- **Boot independence:** no core service (DNS, DHCP, LDAP, SSO, nginx) reads
  OpenBao to *start*. fabricctl renders secrets into each service's config at
  deploy time; if OpenBao is down or sealed, the last rendered config keeps
  running and deploys that need a changed secret wait and report.

**Uses (all four selected):**

| Use | How |
|---|---|
| fabric's own secrets | KV v2 at `fabric/`. `fabric-secrets.yml` is imported once, then OpenBao is the source of truth; fabricctl and fabric-agent authenticate with AppRole (credentials root-only on the host). The plaintext file is removed after import (kept only inside encrypted backups). |
| Secrets for your apps | KV v2 at `apps/`. Humans log in with **Keycloak OIDC** (client `fabric-openbao`); LDAP group → OpenBao policy (e.g. `admins` → admin, `<app>-owners` → `apps/<app>/*`). |
| Dynamic / rotated credentials | Database engine on the fabric Postgres; **static roles** with scheduled rotation for Keycloak's DB user (Keycloak needs a stable password in its config, so fabricctl re-renders and restarts it on rotation). LDAP engine rotates the 389-DS role accounts (`keycloak_admin`, …). Apps can use true dynamic, per-lease DB users. |
| SSH certificate CA | SSH engine signs short-lived user certificates (`bao ssh`/`fabricctl ssh`), principals from LDAP groups; hosts trust the CA key via `TrustedUserCAKeys` (the install-ldap client script gains an option for it). |

The web UI gains a Secrets section (browse/edit `apps/`, rotate, issue SSH
certs) through fabric-agent, which talks to OpenBao with its own AppRole —
the webui container still holds no secrets itself.

## 8. Phases

| Phase | Deliverable | Depends on |
|---|---|---|
| 0 ✅ | Rename to fabric, `fabricctl`, migration from core-template | — |
| 0.5 | Foundations: container hardening, version lock with digest pinning, LF line endings, arm64 + amd64 CI running the real-container suites, Pi preflight | — |
| 0.6 | Signed image channels on GitHub Pages, local registry, `fabric-update` timer with rollback, offline export/import | 0.5 |
| 0.7 | OpenBao: container, auto-unseal from key file, OIDC login via Keycloak, KV for fabric (import `fabric-secrets.yml`) and apps | 0.5 |
| 0.8 | OpenBao: rotated DB/LDAP credentials, SSH certificate CA, web UI Secrets section | 0.7 |
| 1 | `fabricctl init` natively (port 02, 03, 05–10); Ansible kept as fallback | — |
| 2 | `.deb` build + signed apt repo in CI (amd64 + arm64 test runs); `setup.sh` becomes a wrapper | 1 |
| 3 | Kea DHCP + DDNS + reservations (CLI + UI) | 2 |
| 4 | FreeRADIUS 802.1X: EAP-TLS, SCEP, MAB, dynamic VLANs | 3 (MAB uses reservations) |
| 5 | Web UI: PKI, directory, roles, health; remove Ansible | 3, 4 |

Each phase ships on its own and is tested the same way as 1.5.0: real
containers in CI (389-DS, Keycloak, Kea, FreeRADIUS with `eapol_test`).

## 9. Decisions needed

| # | Question | Recommendation |
|---|---|---|
| D1 | Python-in-.deb vs Go binary | Python (§3) |
| D2 | Target OSes | Ubuntu 24.04 (reference: Raspberry Pi 4 GB, arm64), Debian 13, Raspberry Pi OS (Debian 13-based); amd64 + arm64 |
| D3 | Service data under `/opt/<svc>` or `/var/lib/fabric/<svc>` | `/var/lib/fabric` for new installs; keep `/opt` paths on migrated hosts |
| D4 | Kea in a container (host networking) or native package | Container, for parity with the other services and easy pinning |
| D5 | Lease backend: memfile or Postgres | memfile; Postgres only if HA or large lease counts |
| D6 | Which switches/APs must 802.1X support (vendor affects VLAN attributes, CoA, RadSec) | Needs your inventory |
| D7 | Apt repo hosting: GitHub Pages vs Cloudsmith/packagecloud | GitHub Pages (no third party, free, signed) |
| D8 | Keep `setup.sh`/Ansible for remote install after phase 2? | One release as a wrapper, then remove |
| D9 ✅ | Updates | fabric updater + local registry; no Watchtower (§7b) |
| D10 ✅ | Image versions | Signed, CI-tested channel on GitHub Pages, independent of releases; offline export/import + local mirror (§7b) |
| D11 ✅ | Docker privilege | Harden all containers + daemon; userns-remap on by default; rootless opt-in with stated limits (§1b, §7a) |
| D14 ✅ | Product split and privilege model | fabricctl (CLI + root `fabricd`, `fabric-admins` group, no docker group) and the Fabric UI container; one repo, two artifacts (§1a) |
| D15 ✅ | Setup UX | Default change list → Proceed / Advanced; everything settable in `vars.yaml`; `--non-interactive` (§1b) |
| D12 ✅ | Secrets | OpenBao, all four uses, auto-unseal from a local key file (§7c) |
| D13 | Channel signing key custody and soak period before `candidate` → `stable` | Ed25519 key in a protected GitHub environment; 7-day soak |

## References

- OpenBao, [seal types](https://openbao.org/docs/configuration/seal/), [static seal](https://openbao.org/docs/configuration/seal/static/), [KMIP seal](https://openbao.org/docs/configuration/seal/kmip/), [PKCS#11 seal](https://openbao.org/docs/configuration/seal/pkcs11/), [2.3.x release notes](https://openbao.org/community/release-notes/2-3-0/)
- Thales, [CipherTrust k160](https://www.thalestct.com/ciphertrust-data-security-platform/ciphertrust-manager/ciphertrust-k160/)
- ISC, [Kea 3.0, our first LTS version](https://www.isc.org/blogs/kea-3-0/)
- ISC, [Most Kea hooks open-sourced](https://www.isc.org/blogs/kea-hooks-opensourced/)
- ISC KB, [Upgrading to Kea 3.0.0](https://kb.isc.org/docs/things-to-be-aware-of-when-upgrading-to-kea-300)
- Smallstep, [step-ca provisioners (SCEP)](https://smallstep.com/docs/step-ca/provisioners/)
- Smallstep, [EAP-TLS Wi-Fi with RADIUS](https://smallstep.com/blog/eaptls-certificate-wifi/)
