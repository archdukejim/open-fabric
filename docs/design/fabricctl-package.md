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
| `fabric/lib/webui/`, `keycloak_bootstrap.py`, `dirsrv.sh`, `ldap_migrate.*` | Ship as-is inside the package |
| `fabric/jinja/**` templates | Ship as-is (package data) |
| Playbooks 02, 03, 05–10 | **Port** to Python modules (see §4) |
| `package.sh` offline bundles | Becomes an image bundle next to the `.deb` |

Only the "first install" half of the Ansible code needs porting; the
day-2 half is already native.

## 3. Package design

```
fabricctl_<ver>_<arch>.deb
  /usr/bin/fabricctl                      entry point (Python)
  /usr/lib/fabricctl/                     fabric/lib (deploy, webui, seeders, bootstrap)
  /usr/share/fabricctl/templates/         fabric/jinja
  /usr/share/fabricctl/images/            (optional, "fabricctl-images" package) docker save tarballs
  /lib/systemd/system/webui.service       shipped static, config in /etc
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

Same security model (mTLS + Keycloak OIDC + TOTP + CSRF). New sections,
each a thin layer over `fabricctl` actions so CLI and UI never diverge:

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

## 8. Phases

| Phase | Deliverable | Depends on |
|---|---|---|
| 0 ✅ | Rename to fabric, `fabricctl`, migration from core-template | — |
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
| D2 | Target OSes | Debian 13, Ubuntu 24.04, Raspberry Pi OS (Debian 13-based) |
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
