# Open Fabric

> A simple, lightweight, open-source configuration for a network fabric: authoritative DNS, internal PKI, directory, SSO and a secure management web UI — installed on the host it runs on (amd64 or arm64, Raspberry Pi included), secure by default.

---

### Table of Contents
- [Synopsis](#synopsis)
- [Prerequisites and Ecosystem](#prerequisites-and-ecosystem)
  - [Tested Ecosystems](#tested-ecosystems)
  - [Required Images](#required-images)
  - [Deployment Modes](#deployment-modes)
- [Documentation](#documentation)
- [Gaps and Next Tasks](#gaps-and-next-tasks)

---

## Synopsis

**fabric** provisions the core services of a small network — the pieces every LAN needs and nobody wants to hand-wire. Install the `fabricctl` package and run `sudo fabricctl setup` (from a git checkout: `sudo installers/deb/install-from-checkout.sh`, which builds the package, installs it and runs `fabricctl setup`). Managed day-to-day with `fabricctl` or the Open Fabric web UI. It stands up:

| Service | Container | Default names | Purpose |
|---------|-----------|---------------|---------|
| **BIND9** | `bind9` | `dns` | Authoritative DNS (recursion off) with RFC2136/TSIG updates; DNS-over-HTTPS through nginx |
| **nginx** | `nginx` | *(the vhosts below)* | Reverse proxy — HTTPS vhosts, DoH (`/dns-query`), CA certificates page; TCP passthrough for LDAP/LDAPS |
| **Step-CA** | `step-ca` | `ca`, `certs` | Internal PKI — root CA → intermediate → service certificates, ACME; CA certificates for every system on `certs.<domain>` |
| **OpenBao** | `openbao` | `vault` | Secrets: fabric's own secrets, unlocked at boot by a key file, USB stick, security key or KMIP HSM |
| **389 Directory Server** | `dirsrv` | `ldap` | Directory (terminates its own TLS; StartTLS/LDAPS only). On by default (`install_ldap`) |
| **Keycloak** | `keycloak`, `postgres` | `sso` | Identity and Access Management (IAM) and SSO, federated with LDAP. On in the default plan (`install_keycloak`) |
| **Open Fabric** (web UI) | `fabric-web` + host service `fabric-agent` | `fabric` | Control-plane web UI — mTLS client cert + Keycloak OIDC/TOTP (requires Keycloak); unprivileged container, host actions only via `fabric-agent` |
| **Kea DHCP** *(optional)* | `kea-dhcp4`, `kea-ddns` | — | DHCPv4 with lease hostnames in their own dynamic DNS zone (`install_kea`) |
| **FreeRADIUS** *(optional)* | `freeradius` | — | 802.1X: EAP-TLS by linked certificate, MAB by MAC, EAP-TTLS for people, checked against 389-DS (`install_freeradius`) |
| **Fluent Bit** *(optional)* | `fluentbit` | — | Log forwarding to syslog (TLS) and/or Elasticsearch (`install_fluentbit`) |

Everything is rendered from Jinja2 templates. Settings come from a vars file (`--file`) and prompts, and are kept in `/opt/fabric/config/fabric.yaml` (rendered to `/opt/fabric/config/vars.yaml`). Secrets (CA password, TSIG keys, LDAP role-account passwords, OIDC client secrets, …) are generated on the first run and then kept in OpenBao; they are never passed on a command line. Every container runs non-root, with no capabilities and a read-only filesystem (the one documented exception: the optional Kea DHCP server needs the host network and two capabilities); the host firewall and Docker daemon hardening are on by default.

---

## Prerequisites and Ecosystem

### Tested Ecosystems
- **Host:** Ubuntu 24.04 LTS, amd64 or arm64 (Raspberry Pi 4/5, 4 GB+). Setup installs Docker Engine (with compose v2) from Docker's apt repository if it is missing.

### Required Images
Every image is pinned by digest (amd64 + arm64) in
[`fabricctl/images.lock.yaml`](fabricctl/images.lock.yaml); a fabric upgrade never
changes a running image, `sudo fabricctl images update` does. Setup pulls or
builds:
- `nginx` (stable branch), `openbao/openbao`
- `smallstep/step-ca` and `keycloak/keycloak` (optional) — bases of thin local hardened layers (`fabric/stepca:local`, `fabric/keycloak:local`)
- `postgres` (optional, with Keycloak), `fluent/fluent-bit` (optional)
- `debian:trixie-slim` — base of the images built locally from Debian packages: `fabric/bind9:local` (BIND 9.20), `fabric/dirsrv:local` (389 Directory Server), `fabric/web:local` (the web UI, container `fabric-web`), `fabric/kea:local` (Kea 3.0 LTS from ISC's signed repository, optional) and `fabric/freeradius:local` (optional)

### Deployment Modes
- **Install:** `sudo apt install ./fabricctl_<version>_all.deb` (built by `installers/deb/build-deb.sh`, attached to each GitHub release), then `sudo fabricctl setup` — shows the hardened default plan; Proceed or Advanced (relax any item).
- **From a checkout:** `sudo installers/deb/install-from-checkout.sh [setup options]` — builds the .deb from the checkout, installs it with apt, runs `fabricctl setup`; run it again to upgrade to the checkout's code.
- **Non-interactive:** `sudo fabricctl setup --file vars.yaml --non-interactive --yes --approve all` (`--approve` names the host changes allowed without asking: [2.7.1](docs/volume_2_technologies_and_features/2.7.1-host-consent.md#2711-status)).
- **Run:** every service under systemd `fabric.target` — `fabricctl status|start|stop|restart`.
- **Remove:** `sudo fabricctl uninstall` (offers an export of all data first); `sudo apt purge fabricctl` exports to `/var/backups/fabric/` and uninstalls.
- **Offline (Air-gapped):** `--offline` never downloads; packages and images must already be present. Signed offline image bundles (`fabricctl images export/import`) are planned — see [the design](docs/volume_2_technologies_and_features/2.6.1-image-channels.md#2611-image-channels-tested-versions-decoupled-from-releases).

---

## Documentation

Comprehensive documentation is provided in the `docs/` directory to help you understand, deploy, and maintain the infrastructure.

- [**Full Setup Guide**](docs/volume_4_infrequent_ops/4.1.1-requirements.md#4111-overview) — Requirements, the default plan, non-interactive and offline installs, reinstall/uninstall.
- [**Configuration Variables**](docs/volume_2_technologies_and_features/2.1.1-about-settings.md#2111-the-settings-file) — Detailed reference for every setting in the vars file (`fabricctl setup --file`).
- [**Keycloak Deployment**](docs/volume_1_systems_and_services/1.6.2-keycloak.md#1621-overview) — Configuration nuances, architecture, and gotchas for the Keycloak and LDAP integration.
- [**Operations**](docs/volume_3_operations/3.1.1-fabricctl.md#3111-live-configuration-changes-fabricctl) — Live configuration changes via the `fabricctl` interactive editor (DNS records, TSIG keys), lifecycle commands (`setup`, `doctor`, `certs`, `tsig`, `client-cert`, `reinstall`, `uninstall`), TSIG keys for RFC2136 clients.
- [**Open Fabric web UI**](docs/volume_1_systems_and_services/1.5.1-webui-architecture.md#1511-overview) — Browser front end for `fabricctl`: security model, client certificates, first login, troubleshooting.
- [**Design and decisions**](docs/volume_1_systems_and_services/1.1.1-what-fabric-is.md#1111-status) — the `fabricctl` package, the `fabric-agent` privilege model, signed image channels and offline bundles, OpenBao, DHCP, 802.1X, the repository layout (D1–D25).
- [**Architecture and Reference**](docs/volume_1_systems_and_services/1.3.1-topology.md#1311-overview) — In-depth execution flow, directory structures, PKI chains, and template rendering logic.
- [**Test Plan**](docs/volume_4_infrequent_ops/4.8.1-manual-test-plan.md#4811-overview) — Manual test plan and which parts the suites in `tests/` automate.
- [**Subordinate CA Setup**](docs/volume_4_infrequent_ops/4.4.1-subordinate-ca.md#4411-overview) — How to configure this stack as a downstream CA.
- [**Disk encryption**](docs/volume_4_infrequent_ops/4.5.1-disk-encryption.md#4511-overview) — Manual: LUKS for fabric's data, unlocked by the same YubiKey or USB stick.
- [**Function reference**](docs/volume_1_systems_and_services/1.11.1-about-the-reference.md) — every function of `fabricctl/`, `webui/` and `installers/`: purpose, inputs, results, failures and what uses them (generated from the code).

---

## Gaps and Next Tasks

**Missing features:**
- DNS-over-TLS (`:853`) is not exposed yet; there is no automated health check for DoH (`/dns-query`).
- No `fabricctl` command for people: they are added in the web UI (People), in the Keycloak admin console (writable LDAP federation) or with `ldapadd` (as `super_admin`/`user_creator_admin` over StartTLS or LDAPS).
- Signed offline image bundles (`fabricctl images export/import`) and the signed image channel are designed but not built yet.
- No scheduled certificate renewal, monitoring or alerting — service certificates are renewed by `fabricctl setup` or `fabricctl certs`.

**Documentation gaps:**
- IPv6: zones can hold AAAA records (with ULA reverse zones), but `fabric_net` and the published ports are IPv4 only; this is not described in one place.
