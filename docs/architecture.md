# Architecture and Reference

This document provides an in-depth breakdown of the `fabric` infrastructure, covering the request flows, the underlying directory structures (both source and target), and technical references for PKI, DNS, and Jinja2 rendering.

### Table of Contents
- [Repository Structure](#repository-structure)
- [Target Deployment Structure](#target-deployment-structure)
- [System Topology](#system-topology)
- [Dynamic Resource Constraints & Boot Staggering](#dynamic-resource-constraints--boot-staggering)
- [DNS Architecture](#dns-architecture)
- [Request flow — DNS](#request-flow--dns)
- [PKI Chain](#pki-chain)
- [Certificate Relay](#certificate-relay)
- [Request flow — TLS certificate issuance](#request-flow--tls-certificate-issuance)
- [Jinja2 Templates](#jinja2-templates)

---

## Repository Structure

```text
.
├── fabric
│   ├── jinja
│   │   ├── bind9
│   │   ├── webui         # webui.json.j2
│   │   ├── dirsrv          # docker-compose.yml.j2, seed.py, seed/*.ldif.j2
│   │   ├── docker-compose.yml.j2
│   │   ├── nginx
│   │   ├── stepca
│   │   ├── systemd         # wrapper.service.j2, webui.service.j2
│   │   └── vars.yaml.j2
│   ├── lib
│   │   ├── archive.sh
│   │   ├── certs.sh
│   │   ├── webui/        # webui package (server, oidc, tlsclient, actions, views)
│   │   ├── deploy.py
│   │   ├── dirsrv.sh
│   │   ├── dns.sh
│   │   ├── interactive.py
│   │   ├── keycloak_bootstrap.py
│   │   ├── ldap_migrate.py
│   │   ├── ldap_migrate.sh
│   │   ├── manage.sh
│   │   ├── output.sh
│   │   ├── package.sh
│   │   ├── prereqs.sh
│   │   ├── services.sh
│   │   ├── ssh.sh
│   │   ├── tsig.sh
│   │   └── vars.sh
│   ├── playbooks
│   │   ├── 00-controller-check.yml
│   │   ├── 01-gen-vars-and-render-jinja.yml
│   │   ├── 02-target-system-conditioning.yml
│   │   ├── 03-target-service-accounts.yml
│   │   ├── 04-target-file-structure.yml
│   │   ├── 05-target-network.yml
│   │   ├── 06-configure-stepca.yml
│   │   ├── 07-bootstrap-containers.yml
│   │   ├── 08-mint-service-certs.yml
│   │   ├── 09-start-and-configure.yml
│   │   ├── 10-deploy-checks-and-cleanup.yml
│   │   ├── ansible.cfg
│   │   └── fabric-config.yml
│   └── VERSION             # fabricctl version (BUILD is stamped by setup.sh, git-ignored)
├── custom-vars.yaml
├── docs
│   ├── ansible-doc.md
│   ├── architecture.md
│   ├── webui.md
│   ├── install.md
│   ├── keycloak.md
│   ├── lib-doc.md
│   ├── operations.md
│   ├── subordinate.md
│   ├── testplan.md
│   └── vars.md
├── setup.sh
└── tests
```

---

## Target Deployment Structure

```text
/opt/
├── bind9               # Managed: configs and zones updated by installer
│   ├── cache           # Persistent: BIND9 cache data
│   ├── config          # Managed: named.conf*, rndc.key managed by idempotent deploy
│   ├── data            # Managed: db.* (zones) managed by idempotent deploy (except dynamic journals)
│   ├── docker-compose.yml # Managed: Re-rendered and managed by idempotent deploy
│   └── log             # Persistent: BIND9 log directory
├── fabric              # Managed/Persistent mix
│   ├── archive         # Persistent: Automated snapshots and audit logs
│   ├── fabric-secrets.yml # Persistent: Safely preserved secrets for TLS and DNS
│   ├── lib/            # Managed: Utility library with python engines and bash wrappers
│   │   ├── deploy.py   # Managed: Python rendering and state-aware deployment engine
│   │   ├── interactive.py # Managed: Python interactive categorical CLI engine
│   │   └── manage.sh   # Managed: Legacy shell function wrapper
│   ├── src/            # Managed: A full mirror of the deployment repository
│   └── vars.yaml       # User-managed: Safely merged and preserved
├── webui             # Managed (only when install_webui)
│   ├── webui.json    # Managed: webui config incl. OIDC client secret (root, 0600)
│   └── run/web.sock    # Runtime: unix socket (dir root:nginx 0750), mounted into nginx at /srv/webui
├── dirsrv              # Managed/Persistent mix
│   ├── data            # Persistent: 389-DS /data (config, db, logs)
│   │   └── tls         # Managed: server.crt, server.key, ca/*.crt (imported into NSS on start)
│   ├── seed            # Managed: seed.py + 00-config/10-tree/20-accounts/30-aci .ldif (root:ldap 0640)
│   └── docker-compose.yml # Managed
├── nginx               # Managed: config updated by installer
│   ├── docker-compose.yml # Managed: Re-rendered and managed by idempotent deploy
│   ├── certs           # Managed: service certs; client-ca/ca-bundle.pem (webui mTLS trust)
│   ├── config          # Managed: Nginx main and stream configurations
│   │   ├── nginx.conf  # Managed: Main config managed by idempotent deploy
│   │   ├── dns.conf    # Managed: DNS stream routing
│   │   └── conf.d      # External configs (e.g., adguard-web.conf)
│   └── www             # Managed: Static content root
│       ├── certificates# Managed: PKI/Certificate installation portal
│       ├── landing     # Managed: Infrastructure Landing Portal
│       ├── ldap        # Managed: LDAP Client guides
│       ├── manual      # Managed: Core infrastructure manual
│       └── shared      # Managed: Shared CSS/assets
└── stepca              # Persistent: Internally manages certs, keys, and DB
    ├── docker-compose.yml # Managed
    └── data            # Persistent: PKI database, certs, and configurations
        ├── certs       # Persistent
        ├── config      # Persistent
        ├── secrets     # Persistent
        └── templates   # Managed: leaf.tpl and subca.tpl managed by idempotent deploy
```

---

## System Topology

```mermaid
graph TB
    subgraph LAN["LAN (10.0.0.0/22)"]
        CLIENT[Client devices]
        HOST[Pi / bare-metal host]
    end

    subgraph FABRIC["Docker bridge — fabric_net (10.255.0.0/24)"]
        NGINX["nginx :10.255.0.10\nports 53 · 80 · 389 · 443 · 636 · 853"]
        BIND9["bind9 :10.255.0.30\nhost port bind_dns_port → :53"]
        STEPCA["step-ca :10.255.0.40"]
        LDAP["dirsrv (389-DS) :10.255.0.50\n:3389 StartTLS · :3636 LDAPS"]
        KC["keycloak :10.255.0.60"]
    end

    WEB["webui (host systemd)\nunix socket"]

    CLIENT -->|"DNS · HTTPS · LDAPS"| HOST
    HOST --> NGINX
    NGINX -->|"DNS + DoT → :53"| BIND9
    NGINX -->|"DoH /dns-query → :8053"| BIND9
    NGINX -->|"389 → :3389 · 636 → :3636 (TCP passthrough)"| LDAP
    NGINX -->|"mgr.<domain> (mTLS) → unix socket"| WEB
    WEB -->|"OIDC · admin REST"| KC
    KC -->|"LDAPS :3636"| LDAP
    NGINX -->|"HTTPS :443 → :9000"| STEPCA
    BIND9 -.->|"internal DNS"| STEPCA
```

---

## Dynamic Resource Constraints & Boot Staggering

To guarantee stability on resource-constrained hardware (e.g. Raspberry Pi), `fabric` natively enforces dynamic memory ceilings (`mem_limit`) and staggered boot sequences across its Docker containers via the `host_ram_capacity` variable.

### Validation Enforcement
The minimum supported value for `host_ram_capacity` is **3** (GB). If defined (i.e. `> 0`) but less than 3, the `setup.sh` installer and `fabricctl` interactive Python engine will hard-fail to prevent the system from entering an unstable state. A value of `0` denotes an unlimited capacity (the default).

### Docker Compose Memory Ceilings
When `host_ram_capacity` is enabled, Jinja2 automatically injects memory constraints into the `docker-compose.yml` templates for all active services.

**At 3GB Capacity:**
The services are strictly clamped to their minimal footprint, leaving sufficient overhead for the host OS.
- Keycloak: `800M`
- Postgres: `100M`
- 389-DS: `256M` (plus `DS_MEMORY_PERCENTAGE=10`)
- BIND9: `40M`
- Nginx: `15M`
- Step-CA: `30M`

**At 4GB+ Capacity:**
- Keycloak and Postgres proportionally expand to utilize available memory:
  - Keycloak: `1200M * (host_ram_capacity / 4)`
  - Postgres: `200M * (host_ram_capacity / 4)`
- Nginx, BIND9, and Step-CA limits remain capped at their peak efficient usage (`40M`, `80M`, `50M` respectively) and 389-DS at `384M` if `host_ram_capacity == 4`. If the host RAM is 5GB or higher, these lightweight services are fully uncapped as they pose zero threat to system stability.

> [!WARNING]
> **JVM Memory Scaling (Keycloak)**
> Because Keycloak runs on a Java Virtual Machine (JVM), applying a rigid Docker `mem_limit` without instructing the JVM about it can cause blind memory allocation leading to an abrupt OOM-kill. To prevent this, when `host_ram_capacity > 0`, the templates dynamically compute and inject `JAVA_OPTS_APPEND=-Xmx{HeapSize}` into the Keycloak container, sizing the heap to exactly 80% of the calculated Docker ceiling.

### Staggered Boots
If the server cold-boots with a low capacity (`3 <= host_ram_capacity <= 4`), parallel spin-up of all containers can trigger a "thundering herd" resource exhaustion, overloading the CPU and crashing the system before initialization completes.

To mitigate this, artificial boot delays (`ExecStartPre=/bin/sleep N`) are automatically injected into the `systemd` wrapper templates, forcing the following strict sequence:
1. **Postgres**: Boots immediately (`0s`).
2. **Keycloak**: Waits `15s` for Postgres to stabilize.
3. **Rest of Stack**: Nginx, BIND9, 389-DS, and Step-CA wait `30s` (15s after Keycloak).

---

## DNS Architecture

BIND9 runs as an **authoritative-only** server (recursion disabled). It serves:
- Internal forward zones defined in the `dns:` block of `custom-vars.yaml` (`dynamic_zone_var` key resolved to `domain` at render time)
- Each zone with `zone_authority: true` gets an NS A record pointing to `host_ip`
- Reverse zones (PTR) auto-generated from A records — one `/24` `in-addr.arpa` zone per unique subnet; `reverse_zone_names` computed in `vars.yaml.j2`
- ACME challenge and zone records updateable per `tsig_keys[].record_types` (primary keys → `subdomain _acme-challenge`; others → `zonesub`)
- Any additional keys managed by `fabricctl --tsig-keys`

nginx fronts BIND9 on all public DNS ports:

```
:53  TCP/UDP  → bind9:53   plain DNS
:853 TCP      → bind9:53   DNS-over-TLS  (nginx terminates TLS)
:443 /dns-query → bind9:8053          DNS-over-HTTPS (nginx terminates TLS)
```

`bind_dns_port` (default `53`) is the Docker host port mapped to BIND9's internal port 53. BIND9 only listens on port 53 inside the container; Docker publishes it on `bind_dns_port` on the host. If a user installs the `home-core` add-on, `bind_dns_port` is shifted to `5353` to allow AdGuard Home to natively claim port 53.

---

## Request flow — DNS

```mermaid
sequenceDiagram
    participant C as Client
    participant B as bind9 :{{ bind_dns_port }}
    C->>B: DNS query (UDP/TCP)
    B-->>C: authoritative answer
```

---

## PKI Chain

```
Root CA  (offline — manually generated, key never deployed to target)
    ├── Standalone leaf certs  (signed offline)
    └── Step-CA Intermediate CA  (signed offline)
            ├── BIND9 static TLS cert   (offline via step-ca, ~15 years)
            ├── Offline leaf certs      (issued at install time via step-ca)
            │       ├── dns.<domain>    → nginx DoT / DoH
            │       ├── ldap.<domain>   → 389-DS (StartTLS + LDAPS, served by dirsrv itself)
            │       ├── mgr.<domain>    → nginx → webui (only when install_webui)
            │       └── ca.<domain>     → nginx → Step-CA
            ├── webui admin client certs  (fabricctl --client-cert <user>; CN = Keycloak username)
            └── extra_certs  (offline or ACME, per-entry config)
```

The root CA key is generated on the operator's machine before install and is **never deployed to the target**. After signing the intermediate CA, it can be stored offline or destroyed. The installer deploys only `root_ca.crt` (public), `intermediate_ca.crt` (public), and `intermediate_ca.key` (secret — step-ca uses this at runtime). Step-CA serves as the ACME endpoint and signs all runtime leaf certs via its intermediate CA. DNS-01 challenges can be fulfilled via the primary TSIG key (`acme_dns-01`).

The intermediate CA key is automatically derived from the `ica_crt_path` by default exchanging the `.crt` extension for `.key`. This can be overridden explicitly in `custom-vars.yaml` or with `--ica-key <path>`.

Internal CA files are distributed to services as `root_ca.crt` volume mounts. The PKI info page is available at two URLs:

- `https://ca.<domain>/pki/` — hosted on the Step-CA vhost
- `https://landing_page_cname.<domain>/` — dedicated vhost with theme selector and clean download URLs (`/root_ca.crt`, `/intermediate_ca.crt`)

---

## Certificate Relay

Core service certificates (`dns.<domain>`, `ldap.<domain>`, `ca.<domain>`, `landing_page_cname.<domain>`, and `mgr.<domain>` when webui is enabled) are offline Step-CA leaf certs with a 10-year lifetime, issued at install time via `step certificate create`. There is no certbot container or cert-relay service. nginx reads the issued certs directly from the volume paths set during install. The LDAP cert is copied to `/opt/dirsrv/data/tls/` (`server.crt`, `server.key`, `ca/root_ca.crt`, `ca/intermediate_ca.crt`), which 389-DS imports on start. For webui client-certificate verification nginx trusts `/opt/nginx/certs/client-ca/ca-bundle.pem` (intermediate + root).

---

## Request flow — TLS certificate issuance

```mermaid
sequenceDiagram
    participant A as admin (install time)
    participant S as step-ca
    participant N as nginx/certs
    A->>S: step certificate create (offline)
    S-->>A: signed leaf cert (10 years)
    A->>N: deploy cert → nginx reload
```

---

## Jinja2 Templates

All `.j2` files in this repo are rendered by the Ansible playbook or the `fabricctl` deployment engine into `/opt/<service>/`. The `.j2` source files are removed from `/opt` after rendering — only rendered outputs remain on the host.

| Template | Rendered to |
|----------|------------|
| `fabric/jinja/vars.yaml.j2` | `/tmp/fabric-render/vars.yaml` (resolved vars — merged at run time) |
| `fabric/jinja/<service>/docker-compose.yml.j2` | `/opt/<service>/docker-compose.yml` (e.g. nginx, bind9) |
| `fabric/jinja/nginx/nginx.conf.j2` | `/opt/nginx/config/nginx.conf` |
| `fabric/jinja/nginx/www/certificates/index.html.j2` | `/opt/nginx/www/certificates/index.html` |
| `fabric/jinja/nginx/www/ldap/index.html.j2` | `/opt/nginx/www/ldap/index.html` |
| `fabric/jinja/bind9/config/named.conf*.j2` | `/opt/bind9/config/named.conf*` |
| `fabric/jinja/bind9/data/zone.j2` | `/opt/bind9/data/db.<zone>` (forward zones) |
| `fabric/jinja/bind9/data/reverse-zone.j2` | `/opt/bind9/data/db.<octet3>.<octet2>.<octet1>.in-addr.arpa` (PTR — auto-generated) |
| `fabric/jinja/dirsrv/seed/*.ldif.j2` | `/opt/dirsrv/seed/*.ldif` (applied by `seed.py` via `dirsrv.sh seed`) |
| `fabric/jinja/dirsrv/seed.py` | `/opt/dirsrv/seed/seed.py` (copied, not rendered) |
| `fabric/jinja/webui/webui.json.j2` | `/opt/webui/webui.json` |
| `fabric/jinja/systemd/webui.service.j2` | `/etc/systemd/system/webui.service` |
| `fabric/jinja/stepca/leaf.tpl.j2` | `/opt/stepca/data/templates/certs/leaf.tpl` |
| `fabric/jinja/stepca/subca.tpl.j2` | `/opt/stepca/data/templates/certs/subca.tpl` |
