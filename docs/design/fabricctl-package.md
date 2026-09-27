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
  whether to enable `userns-remap` (container root → unprivileged host uid);
  default off. Rootless Docker is not offered: it hides client source IPs
  (breaks BIND/RADIUS ACLs), has no real host networking (breaks Kea DHCP)
  and needs a system-wide low-port sysctl.
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

## 8. Phases

| Phase | Deliverable | Depends on |
|---|---|---|
| 0 ✅ | Rename to fabric, `fabricctl`, migration from core-template | — |
| 0.5 | Foundations: container hardening, version lock with digest pinning, LF line endings, arm64 + amd64 CI running the real-container suites, Pi preflight | — |
| 0.6 | Signed image channels on GitHub Pages, local registry, `fabric-update` timer with rollback, offline export/import | 0.5 |
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

## References

- ISC, [Kea 3.0, our first LTS version](https://www.isc.org/blogs/kea-3-0/)
- ISC, [Most Kea hooks open-sourced](https://www.isc.org/blogs/kea-hooks-opensourced/)
- ISC KB, [Upgrading to Kea 3.0.0](https://kb.isc.org/docs/things-to-be-aware-of-when-upgrading-to-kea-300)
- Smallstep, [step-ca provisioners (SCEP)](https://smallstep.com/docs/step-ca/provisioners/)
- Smallstep, [EAP-TLS Wi-Fi with RADIUS](https://smallstep.com/blog/eaptls-certificate-wifi/)
