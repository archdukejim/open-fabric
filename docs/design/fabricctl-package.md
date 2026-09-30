# Design: `fabricctl` as an apt package, Kea DHCP, 802.1X

Status: **in progress.** Done: phase 0 (rename), container hardening, and phase 1 — the native installer (`fabricctl setup`, §4); Ansible and the playbooks are removed. The rest is proposal.

## 1. Goal

Installing fabric used to mean cloning the repo on a controller, installing
Ansible and running 12 playbooks (~3,000 lines) against the target over SSH.
Today it is `git clone` + `sudo installers/deb/install-from-checkout.sh` on the host itself (native
Python, §4). The goal:

```bash
sudo apt install fabricctl        # one package, one command
sudo fabricctl setup               # interactive, or: fabricctl setup --file vars.yaml
```

Everything setup does (preconditioning, rendering, PKI bootstrap,
containers, checks) already happens locally on the host, driven by
`fabricctl`; the package only changes how the code arrives. Day-2 operations stay the same command (`fabricctl apply`,
`fabricctl dns ...`) and the web UI.

The package and the command share one name. Plain `fabric` is taken
(Python Fabric is packaged as `fabric` in Debian and Ubuntu); `fabricctl` is
free in Debian trixie and Ubuntu 24.04.

Scope beyond the installer: add **Kea DHCP** and **802.1X (FreeRADIUS)**, and
grow the web UI to manage every service.

## 1a. Two products: fabricctl and Open Fabric

| | **fabricctl** — the control | **Open Fabric** (web control) — the control-plane UI |
|---|---|---|
| What | Native apt package on the host | Web app in its own unprivileged container |
| Role | The integration point: installs, configures, updates and secures the whole stack — containers, host firewall, Docker daemon, image updates, OpenBao seals and hardware tokens | Configuration and control plane in the browser: status, DNS/DHCP/users/secrets, triggering operations. Holds no power of its own |
| Stands alone? | **Yes** — everything is possible from the CLI | No — every action is a request to fabricctl's daemon |
| Artifact | `fabricctl` .deb: `fabricctl` CLI + `fabric-agent` daemon + systemd timers | `fabric` container image, installed, pinned (via the channel) and updated by fabricctl |

One repo (`archdukejim/fabric`) builds and tests both; each fabricctl
version declares the web UI image it expects.

**Privilege model (decided):**

- **`fabric-agent`** — root, sandboxed systemd service; the *only* component that
  touches Docker, nftables, systemd, udev and OpenBao seal configuration.
  It exposes a fixed, validated operation API (today's `fabric-agent`,
  generalised) — never "run this command".
- **`fabricctl` CLI** runs as the invoking user and talks to `fabric-agent` over
  a socket restricted to the **`fabric-admins`** group. Membership grants
  fabric's operations, not a root shell. **Nobody is added to the `docker`
  group** (that group is root-equivalent).
- **Open Fabric web UI** reaches `fabric-agent` over its own socket, identified by its
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
| OpenBao unseal | Local key file | USB kill switch, any KMIP key manager, any PKCS#11 HSM, or manual Shamir |
| Image updates | On: signed stable channel, weekly, health-checked with rollback | Off, candidate channel, or offline-only |
| Web UI access | mTLS + Keycloak OIDC + TOTP | TOTP optional |

Non-interactive: `sudo fabricctl setup --file ./vars.yaml` takes every
answer (including all of the above) from the file; the walkthrough only
prompts for missing or invalid values. `--non-interactive` never prompts
and fails on anything missing — for automation and re-provisioning.

Every setting can be changed later (`fabricctl security …`,
`fabricctl vault seal-…`, `fabricctl updates …`, or editing `fabric.yaml` +
`fabricctl apply`). `fabricctl status` and the Open Fabric web UI show a
**security posture** summary that lists every relaxed default as a warning.

## 2. What exists to build on

| Today | Reuse |
|---|---|
| `fabricctl/lib/deploy.py` — native render + deploy + selective reload (what `fabricctl apply` runs) | The core of the installer (`deploy` step) and of day-2 `fabricctl --apply` |
| `webui/` (container app), `fabricctl/lib/agent/` (fabric-agent), `keycloak_bootstrap.py`, `dirsrv.sh` | Ship as-is inside the package |
| `fabricctl/jinja/**` templates | Ship as-is (package data) |
| `fabriclib/setup/` — the native installer (§4) | Ships as-is |
| `fabriclib/` (one operation per file) | The package's library layout from day one |

Both the first-install and day-2 halves are native Python.

## 3. Package design

```
fabricctl_<ver>_<arch>.deb
  /usr/bin/fabricctl                      entry point (Python)
  /usr/lib/fabricctl/                     fabricctl/lib (deploy, agent, webui build context, seeders, bootstrap)
  /usr/share/fabricctl/templates/         fabricctl/jinja
  /usr/share/fabricctl/images/            (optional, "fabricctl-images" package) docker save tarballs
  /lib/systemd/system/fabric-agent.service shipped static, config in /etc
  /lib/systemd/system/fabric-web.service  compose wrapper for the fabric-web container
  /etc/fabric/                            conffiles: fabric.yaml (vars), link-vars.yaml
  /var/lib/fabric/                        secrets, rendered vars, archive/audit
```

- **Depends:** `python3 (>= 3.11)`, `python3-yaml`, `python3-jinja2`,
  `docker.io | docker-ce`, `docker-compose-v2 | docker-compose-plugin`,
  `openssl`, `curl`. All from the distro — no pip, no venv.
- **Architectures:** `all` (pure Python) — one package for amd64 and arm64
  (Raspberry Pi). Images are per-arch and pulled/built at `setup`.
- **Maintainer scripts** stay minimal (create `fabric` system group,
  directories). `postinst` never starts services or touches the network —
  `fabricctl setup` does the real work, so `apt install` is always safe and
  reversible.
- **Config location:** move from `/opt/fabric/config` to `/etc/fabric`
  (config) and `/var/lib/fabric` (state) per FHS; service data stays in
  `/opt/<service>` (or becomes `/var/lib/fabric/<service>`, decision D3).
  `fabricctl` moves an existing `/opt/fabric` on first run.
- **Distribution (decided, D7): GitHub Releases + a signed APT repo on
  GitHub Pages.**
  - Each `v*` tag builds `fabricctl_<ver>_all.deb` (`package.yml`) and
    attaches it to the GitHub Release; the Releases are the one store of
    binaries (never committed to git).
  - A workflow then rebuilds the repository with **reprepro** from all
    Release assets and deploys **only** the repo (`dists/`, `pool/`,
    `public.key`) to the `gh-pages` branch. Source, `conf/` and reprepro's
    `db/` are never published.
  - Suite `stable`, component `main`, architectures `amd64 arm64` (+ `all`,
    which fabricctl is): one suite serves Ubuntu 24.04, Debian 13 and
    Raspberry Pi OS.
  - Signing: a dedicated repo-signing key (`SignWith: <key id>`, with expiry)
    in the Actions secret `GPG_PRIVATE_KEY` (+ passphrase secret); its
    revocation certificate is kept offline; `public.key` published next to
    the repo.
  - Users: `wget -qO- https://archdukejim.github.io/open-fabric/public.key | sudo
    gpg --dearmor -o /usr/share/keyrings/fabric-archive-keyring.gpg`, then
    `deb [signed-by=/usr/share/keyrings/fabric-archive-keyring.gpg]
    https://archdukejim.github.io/open-fabric stable main` in
    `/etc/apt/sources.list.d/fabric.list`, `apt update`, `apt install
    fabricctl`. The Release `.deb` also works directly (`apt install
    ./fabricctl_*.deb`, how the Pi is tested today).
  - Offline sites: the same `dists/` + `pool/` tree can be mirrored to a
    local path or web server (`deb [signed-by=…] file:/srv/fabric-apt stable
    main`).
- **Offline installs:** `fabricctl-images_<ver>_<arch>.deb` (or a tarball)
  carries `docker save` output; `fabricctl setup --offline` loads it.

### Language

| Option | Pros | Cons |
|---|---|---|
| **Python in the .deb (recommended)** | Reuses deploy.py, webui, bootstrap, seeders (~70% of the code); Debian-native deps; `Architecture: all` | Python startup (~150 ms); distro Python version floor |
| Go static binary | Single file, no runtime deps | Full rewrite incl. web UI and Keycloak/LDAP logic; templates must move to Go `text/template` or keep a Jinja dependency |

## 4. Porting the playbooks ✅

Done: each playbook became an idempotent, individually re-runnable step in
`fabricctl/lib/fabriclib/setup/` (`fabricctl setup --step pki`), and the
playbooks were deleted. Mapping:

| Playbook | `fabricctl` step | Notes |
|---|---|---|
| 00 controller check | *(gone)* | No controller any more |
| 00b migrate-from-core | *(dropped)* | Owner decision 2026-09-27: pre-fabric hosts are rebuilt (CA via BYOC, DNS and TSIG keys via the vars file) |
| 01 gen vars + render | `deploy` | deploy.py; settings from `collect_vars` + `choose_plan` |
| 02 system conditioning | `preflight`, `host`, `docker` | Checks, packages + Docker Engine, daemon hardening; later packages come from `Depends:` |
| 03 service accounts | `accounts` | Later a `systemd-sysusers` snippet in the package |
| 04 file structure | `deploy` | deploy.py |
| 05 network | `network`, `firewall` | Resolver drop-in, `fabric_net`; UFW + `DOCKER-USER` |
| 06 configure Step-CA | `pki` | CA init, BYOC import |
| 07 bootstrap containers | `bootstrap` | |
| 08 mint service certs | `certs` | One implementation (`fabriclib/pki/`); also `fabricctl certs` |
| 09 start + configure | `start` | dirsrv seed + keycloak_bootstrap already native |
| 10 checks | `verify` | Also `fabricctl doctor`; web UI later |

**Remote install** (after the `.deb`, phase 2):

```bash
ssh admin@pi 'sudo apt install -y fabricctl && sudo fabricctl setup --file /dev/stdin --non-interactive --yes' < fabric.yaml
```

Until then: clone the repo on the host and run `sudo installers/deb/install-from-checkout.sh`; it is a
thin bootstrap into `fabricctl setup`.

## 5. Kea DHCP

> **Built (roadmap 3):** Kea 3.0 LTS from ISC's repository in a hardened
> host-network container, `dhcp:` in `vars.yaml`, forward DDNS into
> `dhcp.<domain>` (delegated, own key limited to A/AAAA/DHCID,
> `check-with-dhcid`), reservations and leases in the Kea tab and
> `fabricctl dhcp`, setup Advanced option. Memfile leases; config applied by
> restarting Kea (a second or two). **Not yet:** reverse DDNS and skipping
> pool ranges in the generated reverse zones, Kea's HTTPS API (the control
> socket is used, host-only), HA, removing the key and zone when DHCP is
> switched off, DHCP names shown under the BIND tab.

- **Kea 3.0 LTS** (ISC), installed from **ISC's own apt repository**
  (`kea-3-0` on Cloudsmith, signing key pinned by fingerprint, exact package
  version pinned in `images.lock.yaml`) on fabric's pinned Debian base:
  Debian trixie itself ships only 2.6. See D22. As of Kea 3.0 almost all hook libraries are open
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
- **DDNS (decided, D16):** `kea-dhcp-ddns` registers lease hostnames in
  **their own dynamic subzone**, e.g. `laptop.dhcp.home.arpa`. It never
  writes to a zone fabric renders from `vars.yaml`.
  - **Why separate:** apply republishes rendered zones by replacing their
    files, which would wipe dynamic entries. A separate zone also keeps
    DHCP-supplied names (which any client can pick) apart from
    administrator-defined ones.
  - **802.1X:** RADIUS-assigned VLANs are separate subnets, so each VLAN
    can get its own subzone (`iot.dhcp.<domain>`, `guest.dhcp.<domain>`) and
    its own reverse zones.
  - **Subzones:** created empty once, delegated from the parent zone
    (NS + glue in the rendered parent), then left to BIND's journal. Apply
    never rewrites them, and setup re-runs keep their data.
  - **Key:** a dedicated TSIG key, auto-created in `tsig_keys`, with
    `update-policy` `zonesub` limited to A/AAAA/DHCID in the DHCP
    subzone(s) and PTR/DHCID in the DHCP reverse zones. Deny-by-default
    everywhere else, so it cannot touch `home.arpa` itself.
  - **Conflicts:** `ddns-conflict-resolution-mode: check-with-dhcid`, so
    a client cannot take over another client's name.
  - **Names:** `hostname-char-set`/`replacement` sanitise client names;
    clients that send none optionally get a MAC-derived name or none
    (`ddns-generated-prefix`).
  - **Reverse DNS:** fabric's generated reverse zones
    (`dns/reverse_zones.py`) skip any /24 or /64 that contains a Kea
    pool. Kea owns the PTRs there. A static record inside a DHCP subnet
    must then be a Kea **reservation**, not a plain A record; setup
    refuses the overlap with that hint.
  - **Removal:** disabling DHCP deletes the key and the DHCP subzones
    (after a warning listing how many registered hosts disappear).
  - **Web UI:** DHCP-registered hosts are shown read-only, marked *DHCP*,
    under Forward/Reverse zones and on the Kea tab.
- **Reservations ↔ DNS:** a reservation with a hostname produces the A/PTR
  record, so one entry in the UI does both.
- **HA (optional):** Kea HA hook, hot-standby between two fabric nodes.
- **API security:** HTTPS listener on `127.0.0.1`/`fabric_net` only, mTLS
  with a Step-CA client cert held by `fabricctl`/webui.

## 6. 802.1X (FreeRADIUS)

> **Built (roadmap 4, first pass):** FreeRADIUS 3.2 (Debian's packages on
> the pinned Debian base; 3.2 is upstream's supported line, D22) in a
> non-root container without capabilities. **EAP-TLS** against the fabric
> CA and **MAB**, each decided per request by fabric's policy (D23): the
> device linked to the certificate's SHA-256 fingerprint, or owning the MAC,
> must be enabled and hold `network:eap-tls` / `network:mab`; the reply
> carries its role's VLAN. Fail closed when the directory cannot be asked.
> RADIUS clients in `vars.yaml` with secrets in OpenBao, Message-Authenticator
> required per client (BlastRADIUS), `fabricctl radius`, the FreeRADIUS tab
> (clients, recent decisions), setup Advanced option.
>
> **Built (second pass): people by password.** EAP-TTLS/PAP inside a TLS
> tunnel to `radius.<domain>`; the password is checked by binding to 389-DS
> as the person (the directory's lockout counts network logins). Only
> members of groups mapped in `radius_people` may join, each mapping with
> an optional VLAN and a priority (lowest wins), managed with `fabricctl
> radius map-group` and on the FreeRADIUS tab. No TTLS at all while no group
> is mapped. Network logins have no second factor.
>
> **Long-term targets (later passes, all planned):** RadSec (RADIUS over TLS, TCP 2083) with Step-CA
> certificates; CoA / Disconnect from the UI when a device is disabled;
> SCEP enrolment; per-VLAN DHCP subnets and DDNS subzones; MAB keyed off
> Kea reservations. Revocation today is unlinking the certificate or
> disabling the device (effective at the next authentication, no session
> resumption); CRL/OCSP later.

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
- **Dynamic VLANs and access (built: device RBAC in 389-DS):** devices
  live in `ou=devices` and belong to roles in `ou=device-roles`. A role
  grants permissions (`network:eap-tls`, `network:mab`, …) and optionally a
  VLAN (lowest priority number wins). FreeRADIUS looks the device up by
  certificate fingerprint (EAP-TLS) or MAC (MAB), refuses disabled devices
  and devices without the permission, and returns the role's VLAN as
  `Tunnel-Private-Group-Id`. People stay in Keycloak. CoA/Disconnect for
  quarantine from the UI.

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
  step-ca, keycloak, postgres, debian, registry). Locally built images (`dirsrv`, `webui`) start from
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
GitHub Pages (`https://archdukejim.github.io/open-fabric/channels/stable.json`):

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

**Consuming it** — superseded in detail by [image-updates.md](image-updates.md) (D21): hosts *fetch* the validated list automatically unless in offline mode, and apply it only when the admin runs `fabricctl images update` (or turns on `image_auto_apply`). The original outline:

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

> **Status (iteration 1, built):** container, Raft, TLS, `vault.<domain>`,
> static-seal auto-unseal via key slots (fabric-unlock, key in RAM only at start; key-file slot, rotation), one-time
> init (recovery keys to `~/fabric-admin`), root token revoked, AppRoles
> `fabric-setup` / `fabric-agent` bound to fabric_net, KV v2 `fabric/` and
> `apps/`, declarative audit log, `fabricctl vault status`, web UI status tab,
> doctor checks, backup/reinstall; `fabric-secrets.yml` imported into
> `fabric/secrets` (verified, shredded, marker file; OpenBao locked → setup
> stops, never regenerates). Since then built: unlock methods (key file,
> USB sticks — tested on a Pi —, PKCS#11 security keys and KMIP HSMs, the
> latter two against SoftHSM2 / PyKMIP only), Keycloak sign-in to OpenBao's
> own UI per role bundle, break glass. **Not yet:** rotated credentials,
> SSH CA.

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
- **Unlock methods = key slots (decided, D17).** OpenBao keeps one seal:
  the built-in `static` seal with one 32-byte key **K**. fabric decides how
  K reaches it, the way LUKS does for disks: K is stored *wrapped* in one or
  more **slots**, and **any one enabled slot unlocks** (a later option can
  require several together: k-of-n across slots).

  | Slot | K is… | Present when | Tested against |
  |---|---|---|---|
  | Local file | in `/etc/fabric/openbao/` (openbao user, 0400) | always (no kill switch while this slot exists) | real image |
  | USB stick (one slot per stick) | on the stick; the stick is recognised by filesystem UUID + USB serial and unknown sticks are refused | the stick is plugged into the host | loop device; real stick on a Pi 5 |
  | Security key (PKCS#11: YubiKey, Nitrokey, SmartCard-HSM, …) | encrypted by a non-exportable RSA-2048 key inside the token (RSA-OAEP; SHA-1, the digest every token supports); PIN root-only on the host; touch via the key's own policy (set with the vendor tool) | the token is plugged in | SoftHSM2 (hardware tokens untested) |
  | HSM / key manager (KMIP: CipherTrust, Fortanix, Entrust, IBM, Cosmian, OVH, …) | encrypted by an active AES key on the device, over mutual TLS | the device is reachable and authorises this client | PyKMIP |

  Keypad-encrypted USB drives (Apricorn, IronKey, iStorage, …) are USB
  stick slots: unlocked by PIN on the drive, then read like any stick.
  Examples of devices are not a support list: fabric supports interfaces
  (plain storage, PKCS#11, KMIP). Vendor specifics (licensing, login rules,
  enabled algorithms) are the device's; the UI says which simulator a slot
  type was tested against.

  - **fabric-unlock** (host unit, before `openbao`; re-run by udev on
    insert): tries every slot, writes K to `/run/fabric/openbao/<key id>.key`
    (tmpfs, openbao user, 0400). OpenBao's static seal reads it and
    unseals; the file is then wiped. No slot present → OpenBao stays sealed
    (unhealthy) while every core service keeps running. Last slot device
    removed → `bao operator seal` immediately (kill switch), unless a
    local-file slot exists, which the UI states.
  - **HSM work happens on the host**, not in the OpenBao container: no
    vendor libraries, plugins or device passthrough in the container, which
    stays capability-free and read-only (and the Alpine/musl vs glibc
    vendor-library problem disappears).
  - **Trade-off, stated in the docs:** unlike OpenBao's native HSM seals,
    K exists briefly in host RAM while unsealing. Root on the running host
    could take it, and could equally read the unsealed vault from memory.
  - **Web UI** (OpenBao tab → Unlock methods) and `fabricctl vault slot …`:
    list slots (type, label, device id, added, Test); **add** a slot (only
    while unlocked); **remove** (never the last one); **rotate K** (new key,
    re-wrapped into every remaining slot, OpenBao moved over with the static
    seal's `previous_key` → `current_key` rotation). Rotation is the answer
    to a lost stick or token: its slot stops working without being needed.
    Every change is audited and needs the host name typed as confirmation.
  - With auto-unseal, OpenBao's recovery keys cannot decrypt the vault:
    losing every slot loses the data. The UI warns while only one
    removable slot exists and recommends a second (a backup stick in the
    safe, or a second token with the same imported key).
  - Security keys: K is imported into (or wrapped by) the token's key.
    Tokens that allow import (YubiKey PIV/OpenPGP, SmartCard-HSM) can hold
    the same key in two tokens; otherwise the backup is another slot type.
  - Cloud KMS (AWS/Azure/GCP) would be another slot type, but it needs the
    internet to unseal (against the offline requirement): not offered
    unless asked for.
  - Build order: slot store + fabric-unlock + local-file slot (replacing
    today's direct key file), USB stick slots, security keys, KMIP.

- **USB stick slots — details:**
  - The stick is plugged into the fabric host. The UI lists removable USB
    block devices; the admin picks one and types the host name to confirm
    (it is wiped). fabric writes K (key id + checksum), verifies it, records
    the stick's UUID and serial, and tests the slot.
  - Mounted read-only at `/run/fabric/key-usb/<uuid>` only while
    fabric-unlock reads it (tmpfs mount point, never under `/opt`).
  - Limits, stated in the UI: a plain stick can be copied by anyone who
    holds it for a moment (rotate if one goes missing); someone holding
    the host and a slot device together can unseal; a stick left in the
    host is the same as the local file.

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

## 7d. Disk encryption: LUKS unlocked by a security key (decided, D18 — revised)

Owner decision (2026-09-29): **fabric does not set up disk encryption.**
People do it themselves, once, at the console; fabric documents how, in the
web UI (OpenBao → Disk encryption) and in
[disk-encryption.md](../disk-encryption.md): a LUKS2 data volume for `/opt`
and `/etc/fabric`, unlocked by the **same YubiKey** (its FIDO2 application,
`systemd-cryptenroll`; OpenBao uses its PIV application) or the **same USB
stick** (a LUKS key file beside fabric's `fabric-vault/` folder, read by
`/etc/crypttab`), always with a passphrase slot and a header backup. The
planned `fabricctl disk` commands, doctor check and Overview light are
dropped. The guide is untested with hardware.

## 7e. Access control for people: RBAC across the stack (decided, D19; built)

Today the web UI has one role (`fabric-admin`) that can do everything. The
389-DS roles of §5/§6 are what *devices* may do on the network; this is
what *people* may do in fabric.

- **Permissions** per area and action, each a Keycloak realm role:
  `dns:read|write`, `tsig:manage`, `pki:read|issue|sign|link-device`,
  `devices:read|enroll|admin`, `roles:admin` (device roles),
  `radius:read|admin` (802.1X), `people:read|create|reset`,
  `vault:status|unlock-methods`, `audit:read`, `system:admin`
  (services, updates, settings).
- **Bundles** are Keycloak composite roles granted to LDAP groups; fabric
  ships these, admins add their own in Keycloak:

  | Bundle | Can |
  |---|---|
  | Admin | everything (today's `fabric-admin`) |
  | Network operator | DNS records and zones, TSIG keys, reverse zones, DHCP (Kea) — **no** device management |
  | Equipment operator | all 802.1X (FreeRADIUS) and 389-DS hardware management: devices, device roles, enable/disable, link certificates to devices |
  | PKI operator | sign CSRs, issue key pairs, convert certificates, link issued certificates to devices (TSIG keys belong to Network operator) |
  | Helpdesk | create realm users, reset their sign-in (password, TOTP), enrol devices; read-only elsewhere |
  | Auditor | read every tab and the audit log; changes nothing |

- **Enforced twice.** The web UI shows only what the user may do; the
  fabric-agent re-checks every call against the user's **signed Keycloak
  token**, which the web UI forwards and the agent verifies itself
  (signature via the realm's keys, issuer, audience, expiry, roles). A
  compromised web UI container cannot act beyond the signed-in user.
- **OpenBao** uses the same roles: each bundle maps to OpenBao policies
  through the OIDC role's claims (built: Admin → `fabric-admin`, Auditor →
  `fabric-auditor` via external identity groups; others not admitted).
- **Built:** permission roles, bundles and their groups in Keycloak and
  389-DS, the agent's token check and route table, pages that follow the
  permissions, token renewal (a removed role ends the session), the
  Helpdesk people pages (add a person, reset a sign-in; fabric-group
  members only by an admin).
- **The host CLI** stays root (`sudo fabricctl` = everything); RBAC covers
  the web UI and its agent API. Step-up sign-in (5 min) and the typed host
  name stay on dangerous changes whatever the role.

## 7f. Log forwarding (decided, D20; built)

Optional, off by default: send **all** logs to a syslog server and/or an
Elastic-style aggregator (Elasticsearch, OpenSearch, anything that speaks
the Elasticsearch bulk API) for analysis. **Fluent Bit** is the collector,
an optional stack component like Keycloak: `install_fluentbit` (asked
during `fabricctl setup`, hot-addable/removable later), its own hardened
container and systemd unit under `fabric.target`, a Fluent Bit section in
the web UI (destinations, last delivery, backlog) and in `fabricctl status`.

- **What:** fabric's audit log, OpenBao's audit log (secrets already
  HMAC'd), every container's output (nginx access/error, Keycloak events,
  389-DS access/errors, BIND queries and updates, Step-CA, Kea,
  FreeRADIUS), fabric-agent and fabricctl, and the host's journal.
- **How:** the Fluent Bit container (arm64 + amd64, ~20–40 MB, memory
  limit like the rest, non-root, read-only root, no capabilities) reads the
  journal and the log files read-only, with a disk buffer so nothing is
  lost while a destination is down. Image pinned by digest.
  - Syslog: RFC 5424 over TCP+TLS (UDP only as an explicit setting).
  - Elastic/OpenSearch: HTTPS, API key or basic auth.
  - TLS verified (fabric CA or a CA you give); credentials in OpenBao, never
    in `vars.yaml`.
- **Settings** in `vars.yaml` (`log_forwarding: {syslog: …, elastic: …}`),
  shown in `fabricctl status` and the Overview tab (last delivery, backlog).
  Local logs stay where they are; forwarding is a copy.

## 8. Phases

| Phase | Deliverable | Depends on |
|---|---|---|
| 0 ✅ | Rename to fabric, `fabricctl` (no migration: pre-fabric hosts are rebuilt) | — |
| 0.5 | Foundations: container hardening, version lock with digest pinning, LF line endings, arm64 + amd64 CI running the real-container suites, Pi preflight | — |
| 0.6 | Signed image channels on GitHub Pages, local registry, `fabric-update` timer with rollback, offline export/import | 0.5 |
| 0.7 ✅ | OpenBao: container, unlock methods (key file, USB, PKCS#11), OIDC login via Keycloak for OpenBao's own UI, break glass, KV for fabric (secrets moved in) and apps | 0.5 |
| 0.8 | OpenBao: KMIP unlock, rotated DB/LDAP credentials, SSH certificate CA (secrets are browsed in OpenBao's own UI) | 0.7 |
| 1 ✅ | Native installer `fabricctl setup` (all playbooks ported); Ansible removed | — |
| 2 | `.deb` build + signed apt repo in CI (amd64 + arm64 test runs); `setup.sh` becomes a wrapper | 1 |
| 3 ✅ | Kea DHCP + DDNS + reservations (CLI + UI) | 2 |
| 4 (two passes ✅) | FreeRADIUS 802.1X: EAP-TLS, MAB, dynamic VLANs ✅; people by password (EAP-TTLS) ✅; RadSec, CoA, SCEP later | 3 (MAB uses reservations) |
| 5 | Web UI: PKI, directory, roles, health | 3, 4 |

Each phase ships on its own and is tested the same way as 1.5.0: real
containers in CI (389-DS, Keycloak, Kea, FreeRADIUS with `eapol_test`).

## 9. Decisions needed

| # | Question | Recommendation |
|---|---|---|
| D1 | Python-in-.deb vs Go binary | Python (§3) |
| D2 | Target OSes | Ubuntu 24.04 (reference: Raspberry Pi 4 GB, arm64), Debian 13, Raspberry Pi OS (Debian 13-based); amd64 + arm64 |
| D3 | Service data under `/opt/<svc>` or `/var/lib/fabric/<svc>` | `/var/lib/fabric` for new installs; keep `/opt` paths on existing hosts |
| D4 | Kea in a container (host networking) or native package | Container, for parity with the other services and easy pinning |
| D5 | Lease backend: memfile or Postgres | memfile; Postgres only if HA or large lease counts |
| D6 | Which switches/APs must 802.1X support (vendor affects VLAN attributes, CoA, RadSec) | Needs your inventory |
| D7 ✅ | Apt repo hosting | GitHub Releases for the `.deb` + reprepro-built signed repo on GitHub Pages (`gh-pages`), dedicated signing key in Actions secrets (§2 Distribution) |
| D8 ✅ | Keep Ansible for remote install? | No: removed. `setup.sh` is a local bootstrap; remote = ssh + apt (phase 2) |
| D9 ✅ | Updates | fabric updater + local registry; no Watchtower (§7b) |
| D10 ✅ | Image versions | Signed, CI-tested channel on GitHub Pages, independent of releases; offline export/import + local mirror (§7b) |
| D11 ✅ | Docker privilege | Harden all containers + daemon; userns-remap on by default; rootless opt-in with stated limits (§1b, §7a) |
| D14 ✅ | Product split and privilege model | fabricctl (CLI + root `fabric-agent` — deliberately not `fabricd`, FRRouting's OpenFabric daemon — `fabric-admins` group, no docker group) and the Open Fabric web UI container; one repo, two artifacts (§1a) |
| D15 ✅ | Setup UX | Default change list → Proceed / Advanced; everything settable in `vars.yaml`; `--non-interactive` (§1b) |
| D12 ✅ | Secrets | OpenBao, all four uses, auto-unseal from a local key file (§7c) |
| D18 ✅ | Disk encryption | Done by people themselves: fabric ships a manual guide (web UI + docs/disk-encryption.md) for LUKS2 with the same YubiKey (FIDO2) or USB stick; no `fabricctl disk` (§7d, revised 2026-09-29) |
| D17 ✅ | How OpenBao is unlocked | Key slots (local file, USB sticks, PKCS#11 security keys, KMIP HSMs); any one enabled slot unlocks; handled on the host by fabric-unlock; vendor-neutral (§7c) |
| D16 ✅ | Where Kea registers DHCP hostnames | A separate dynamic subzone per DHCP scope (`dhcp.<domain>`, per-VLAN subzones with 802.1X); never the rendered zones (§5) |
| D19 ✅ | Who may do what (people) | RBAC: per-area permissions as Keycloak realm roles, bundles (Admin, Network operator without device management, Equipment operator for 802.1X + 389-DS hardware, PKI operator, Helpdesk, Auditor); the agent verifies the user's signed token on every call; OpenBao policies follow the same roles (§7e) |
| D20 ✅ | Central logging | Fluent Bit as an optional stack component (`install_fluentbit`, chosen at setup, hot-addable): forwards all logs to syslog (RFC 5424, TLS) and/or Elasticsearch/OpenSearch, disk-buffered, credentials in OpenBao (§7f) |
| D21 | Image updates (validation pipeline and host side) | Daily watcher → regression on amd64 + arm64 incl. an upgrade test → pass: PR auto-merged, signed list published; fail: GitHub issue. Hosts fetch the list automatically unless offline, apply only on command (or opt-in auto-apply), prune old fabric images ([image-updates.md](image-updates.md)) |
| D25 ✅ | Repository layout | Three product folders: `fabricctl/` (the Linux host side), `webui/` (the control-plane container) and `installers/deb/` (the Debian package wrapper; more formats as siblings). The installed tree (`/usr/lib/fabricctl/fabric`, `/opt/fabric`) is unchanged: `installers/deb/assemble-tree.sh` maps the folders onto it, so installs upgrade in place. The web UI stays in this repository (it changes together with the agent API it calls; split only once that API is versioned and CI publishes images). `setup.sh` became `installers/deb/install-from-checkout.sh`: a checkout installs through the same .deb as a release |
| D24 ✅ | Names | The repository is `open-fabric` and the web UI is shown as "Open Fabric" (subtitle *web control*). Everything else keeps its name: the package and command `fabricctl`, `/opt/fabric`, `/etc/fabric`, `fabric.target` and the `fabric-*` units, `fabriclib`, the Keycloak `fabric:*` roles, OpenBao's `fabric/` path, the image names — renaming those would need migration code on every install for no user benefit. The root daemon is `fabric-agent`, never `fabricd` (FRRouting's OpenFabric daemon). The repository is renamed before the image channel and APT repository are published on GitHub Pages (Pages URLs do not redirect) |
| D23 ✅ | How FreeRADIUS decides | fabric's own policy (python3 module) asks 389-DS on every request, as the read-only `cn=radius_reader`, over verified LDAPS: nothing is cached or exported, so a disabled device or an unlinked certificate is refused at its next authentication. EAP-TLS devices are found by the SHA-256 fingerprint of the presented certificate (recorded during verification, keyed by serial, since FreeRADIUS exposes no fingerprint); MAB by MAC. People (EAP-TTLS/PAP) are checked by binding as the person, then by membership of a mapped group (`radius_people`). The directory unreachable means Reject (fail closed) |
| D22 ✅ | Which upstream line | LTS or extended-support wherever the project has one (BIND 9.20 ESV, Kea 3.0 LTS, Postgres majors, nginx stable, Debian stable, Ubuntu LTS). Projects without one (OpenBao, Keycloak, Step-CA, Fluent Bit) support only their latest release: follow it, patch releases automatically, never a major by itself (D21). A distro package that lags the upstream LTS (Kea: Debian 2.6 vs 3.0) comes from the upstream's signed repository instead |
| D13 | Channel signing key custody and soak period before `candidate` → `stable` | Ed25519 key in a protected GitHub environment; 7-day soak |

## References

- OpenBao, [seal types](https://openbao.org/docs/configuration/seal/), [static seal](https://openbao.org/docs/configuration/seal/static/), [KMIP seal](https://openbao.org/docs/configuration/seal/kmip/), [PKCS#11 seal](https://openbao.org/docs/configuration/seal/pkcs11/), [2.3.x release notes](https://openbao.org/community/release-notes/2-3-0/)
- ISC, [Kea 3.0, our first LTS version](https://www.isc.org/blogs/kea-3-0/)
- ISC, [Most Kea hooks open-sourced](https://www.isc.org/blogs/kea-hooks-opensourced/)
- ISC KB, [Upgrading to Kea 3.0.0](https://kb.isc.org/docs/things-to-be-aware-of-when-upgrading-to-kea-300)
- Smallstep, [step-ca provisioners (SCEP)](https://smallstep.com/docs/step-ca/provisioners/)
- Smallstep, [EAP-TLS Wi-Fi with RADIUS](https://smallstep.com/blog/eaptls-certificate-wifi/)
