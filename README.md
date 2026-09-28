# fabric

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

**fabric** provisions the core services of a small network — the pieces every LAN needs and nobody wants to hand-wire — with one command: `sudo ./setup.sh` (which runs `fabricctl setup`). Managed day-to-day with `fabricctl` or the web UI. It stands up:

| Service | Container | Default CNAMEs | Purpose |
|---------|-----------|----------------|---------|
| **BIND9** | `bind9` | `dns` | Authoritative DNS + DNS-over-HTTPS + DNS-over-TLS |
| **nginx** | `nginx` | *(various)* | Reverse proxy — DNS/DoT/DoH/HTTPS; TCP passthrough for LDAP/LDAPS |
| **Step-CA** | `step-ca` | `ca`, `certificates` | Internal PKI — root CA → intermediate → ACME |
| **389 Directory Server** | `dirsrv` | `ldap` | Directory services (terminates its own TLS; StartTLS/LDAPS only) |
| **Keycloak** | `keycloak`, `postgres` | `sso` | Identity and Access Management (IAM) and SSO, integrated with LDAP |
| **webui** | `webui` + host service `fabric-agent` | `mgr` | Management web UI — mTLS client cert + Keycloak OIDC/TOTP (requires Keycloak); unprivileged container, host actions via `fabric-agent` |

Everything is rendered from Jinja2 templates. Settings come from a vars file (`--file`, or `custom-vars.yaml` in the checkout) and prompts, and are kept in `/opt/fabric/config/fabric.yaml`. Secrets (CA password, TSIG keys, LDAP role-account passwords, webui OIDC secret) are generated on the first run into `/opt/fabric/config/fabric-secrets.yml` (`0600`) and never passed on a command line. Every container runs non-root, with no capabilities and a read-only filesystem; the host firewall and Docker daemon hardening are on by default.

---

## Prerequisites and Ecosystem

### Tested Ecosystems
- **Host:** Ubuntu 24.04 LTS, amd64 or arm64 (Raspberry Pi 4/5, 4 GB+). Setup installs Docker Engine (with compose v2) from Docker's apt repository if it is missing.

### Required Images
Setup pulls or builds these images on the host:
- `nginx:latest`
- `ubuntu/bind9:latest`
- `smallstep/step-ca:latest`
- `fabric/dirsrv:local` (optional, if LDAP is enabled) — 389 Directory Server built locally from Debian stable packages (`fabric/jinja/dirsrv/build`); `fabricctl --update-containers` rebuilds it with the latest security updates
- `keycloak/keycloak:latest` (optional, if Keycloak is enabled)
- `postgres:latest` (optional, if Keycloak is enabled)

### Deployment Modes
- **Install:** `sudo apt install ./fabricctl_<version>_all.deb`, then `sudo fabricctl setup` — shows the hardened default plan; Proceed or Advanced (relax any item).
- **Non-interactive:** `sudo fabricctl setup --file vars.yaml --non-interactive --yes`.
- **Run:** every service under systemd `fabric.target` — `fabricctl status|start|stop|restart`.
- **Offline (Air-gapped):** `--offline` never downloads; packages and images must already be present. Signed offline image bundles (`fabricctl images export/import`) are planned — see [the design](docs/design/fabricctl-package.md#7b-image-channels-tested-versions-decoupled-from-releases).

---

## Documentation

Comprehensive documentation is provided in the `docs/` directory to help you understand, deploy, and maintain the infrastructure.

- [**Full Setup Guide**](docs/install.md) — Requirements, the default plan, non-interactive and offline installs, reinstall/uninstall.
- [**Configuration Variables**](docs/vars.md) — Detailed reference for all customizable variables in `custom-vars.yaml`.
- [**Keycloak Deployment**](docs/keycloak.md) — Configuration nuances, architecture, and gotchas for the Keycloak and LDAP integration.
- [**Operations**](docs/operations.md) — Live configuration changes via the `fabricctl` interactive editor (DNS records, TSIG keys), lifecycle commands (`setup`, `doctor`, `certs`, `tsig`, `client-cert`, `reinstall`, `uninstall`), TSIG keys for RFC2136 clients.
- [**webui Management UI**](docs/webui.md) — Browser front end for `fabricctl`: security model, client certificates, first login, troubleshooting.
- [**Roadmap: `fabricctl` apt package, Kea DHCP, 802.1X**](docs/design/fabricctl-package.md) — `apt install fabricctl`, the `fabricd` privilege model, signed image channels and offline bundles, OpenBao, DHCP and 802.1X.
- [**Architecture and Reference**](docs/architecture.md) — In-depth execution flow, directory structures, PKI chains, and template rendering logic.
- [**AI Test Plan**](docs/testplan.md) — Automated testing scripts and procedures.
- [**Subordinate CA Setup**](docs/subordinate.md) — How to configure this stack as a downstream CA.
- [**Library Reference**](docs/lib-doc.md) — The `fabriclib` Python package and the remaining shell modules.

---

## Gaps and Next Tasks

The following gaps were identified while writing this document:

**Missing features:**
- No automated health check for DoH (`/dns-query`) or DoT (`:853`) endpoints — these are core delivery paths.
- No LDAP user/group provisioning tooling — `vars.yaml` defines the OU structure but adding actual users requires manual `ldapadd` (as `super_admin`/`user_creator_admin` over StartTLS or LDAPS) or the Keycloak admin console (writable LDAP federation).

**Hardening gaps:**
- Docker images are still referenced by `:latest` tag by default. All image references are now centralized in `vars.yaml` (`image_nginx`, `image_bind9`, `image_stepca`) making digest pinning straightforward — but the defaults remain mutable `:latest` tags.

**Documentation gaps:**
- `fabric/lib/manage.sh --mint-certs` ACME mode references a Portainer webhook URL but its expected format and behavior are not documented.
- IPv6 is not addressed in `vars.yaml` or `fabric/jinja/docker-compose.yml.j2`, despite BIND9 listening on `listen-on-v6 { any; }`.
- No monitoring or alerting integration — cert expiry requires manual verification.

<!-- readme-version: cdab97e -->
