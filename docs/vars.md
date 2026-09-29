# fabric Configuration Variables

This document details all available configuration variables that can be defined in your `custom-vars.yaml` file. 

The `custom-vars.yaml` file acts as the single source of truth for rendering the infrastructure environment. While only a handful of variables are required (and included in the default `custom-vars-tpl.yml`), you may optionally define any of the variables below to override the backend system defaults.

---

## 1. Global Options
These variables define top-level identity and basic settings.

### `domain`
**Description:** The base domain for the local network (e.g. `lan.example.com`). **Required.**

**Default Value:** *(Mandatory - Template: `example.com`)*

**Effected Jinja Templates:**
- `bind9/data/reverse-zone.j2`
- `bind9/data/zone.j2`
- `docs/testplan.md.j2`
- `nginx/www/certs/index.html.j2`
- `nginx/www/certs/install-certs.sh.j2`
- `vars.yaml.j2`

### `domain_file`
**Description:** The domain name formatted for use as a filename (dots replaced with underscores).

**Default Value:** `domain` with `.` replaced by `_`

**Effected Jinja Templates:**
- `nginx/nginx.conf.j2`
- `nginx/www/certs/index.html.j2`
- `nginx/www/certs/install-all-ubuntu.sh.j2`
- `nginx/www/certs/install-certs.sh.j2`
- `vars.yaml.j2`

### `hostname`
**Description:** The hostname of the Docker host server. **Required.**

**Default Value:** *(Mandatory - Template: `fabric`)*

**Effected Jinja Templates:**
- `vars.yaml.j2`

### `friendly_name`
**Description:** A friendly display name for organizations or the CA.

**Default Value:** `"Example Org"`

**Effected Jinja Templates:**
- `nginx/www/certs/index.html.j2`
- `nginx/www/certs/install-certs.sh.j2`
- `nginx/www/certs/install-chrome-ubuntu.sh.j2`
- `nginx/www/certs/install-firefox-ubuntu.sh.j2`
- `nginx/www/certs/install-python-ubuntu.sh.j2`
- `nginx/www/landing/index.html.j2`
- `nginx/www/manual/index.html.j2`
- `vars.yaml.j2`

### `service_mark`
**Description:** Text to display with the Service Mark (`℠`) symbol in the footer.

**Default Value:** `""`

### `trademark`
**Description:** Text to display with the Trademark (`™`) symbol in the footer.

**Default Value:** `""`

### `copyright`
**Description:** Copyright holder/year to display with the Copyright (`©`) symbol in the footer.

**Default Value:** `""`

### `contact_email`
**Description:** Contact email address displayed in the footer.

**Default Value:** `""`

### `contact_phone`
**Description:** Contact phone number displayed in the footer.

**Default Value:** `""`

### `address_line1`
**Description:** Primary address line displayed in the footer.

**Default Value:** `""`

### `address_line2`
**Description:** Secondary address line (e.g., Suite, City, State) displayed in the footer.

**Default Value:** `""`

### `care_of`
**Description:** Attribution text displayed with the Care Of (`℅`) symbol in the footer. Replaces the legacy `vendor` variable.

**Default Value:** `""`

### `system_timezone`
**Description:** The timezone for the server/containers.

**Default Value:** `"America/New_York"`

**Effected Jinja Templates:**
- `vars.yaml.j2`

### `deploy_base_dir`
**Description:** The base directory on the host where project data and configs will be deployed.

**Default Value:** `"/opt"`

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `bind9/docker-compose.yml.j2`
- `webui/docker-compose.yml.j2`
- `dirsrv/docker-compose.yml.j2`
- `docs/testplan.md.j2`
- `keycloak/docker-compose.yml.j2`
- `nginx/docker-compose.yml.j2`
- `postgres/docker-compose.yml.j2`
- `stepca/docker-compose.yml.j2`
- `systemd/fabric-agent.service.j2`
- `systemd/wrapper.service.j2`
- `vars.yaml.j2`

## 2. Networking & DNS
> [!WARNING]
> Editing core networking configurations post-deployment can impact routing and require widespread service restarts. Proceed with caution.

These settings dictate how containers route traffic and how the BIND9 DNS server handles resolution.

### `host_ip`
**Description:** The primary IP address of the Docker host. **Required.**

**Default Value:** *(Mandatory - Template: `192.168.1.100`)*

**Effected Jinja Templates:**
- `bind9/data/zone.j2`
- `docs/testplan.md.j2`
- `nginx/docker-compose.yml.j2`
- `vars.yaml.j2`

### `lan_cidr`
**Description:** The subnet representing your local LAN clients.

**Default Value:** *(Mandatory - Template: `192.168.1.0/24`)*

**Effected Jinja Templates:**
- `docs/testplan.md.j2`
- `vars.yaml.j2`

### `lan_gateway`
**Description:** The default gateway router IP for your LAN.

**Default Value:** *(Mandatory - Template: `192.168.1.1`)*

**Effected Jinja Templates:**
- `vars.yaml.j2`

### `fabric_subnet`
**Description:** The internal Docker bridge subnet for the fabric services.

**Default Value:** `10.255.0.0/24`

**Effected Jinja Templates:**
- `vars.yaml.j2`

### `use_host_dns`
**Description:** If `true`, the host's existing `resolv.conf` is used during deployment. If `false`, systemd-resolved is reconfigured to use `dns_server`.

**Default Value:** `true`

**Effected Jinja Templates:**
- `vars.yaml.j2`

### `dns_server`
**Description:** External upstream DNS server to forward queries to (e.g., `8.8.8.8`).

**Default Value:** `"8.8.8.8"`

**Effected Jinja Templates:**
- `vars.yaml.j2`

### `bind_dns_port`
**Description:** The port BIND9 listens on for standard DNS (UDP/TCP).

**Default Value:** `5353`

**Effected Jinja Templates:**
- `bind9/config/named.conf.options.j2`
- `bind9/docker-compose.yml.j2`
- `docs/testplan.md.j2`
- `vars.yaml.j2`

### `bind9_doh_port`
**Description:** The port BIND9 listens on for DNS-over-HTTPS.

**Default Value:** `8053`

**Effected Jinja Templates:**
- `bind9/config/named.conf.options.j2`
- `bind9/config/named.conf.tls.j2`
- `nginx/nginx.conf.j2`
- `vars.yaml.j2`


### Advanced DNS Dictionary Variables

*   **`dns`**: A structured dictionary that defines your DNS records. Keys represent zone files (where `dynamic_zone_var` automatically correlates to your base `domain`).
*   **`bind_acls`**: Lists of IP ranges granted query/update permissions.
*   **`tsig_keys`**: TSIG keys for RFC2136 dynamic updates (e.g. DNS-01 from nginx-proxy-manager): `name`, optional `secret` (keep an existing key), `records`, `any_name`, `record_types`, `algorithm`, `domain`, `primary`, `acls`, `out`. Update rights are deny-by-default. Fields and grants: [operations.md](operations.md#tsig-keys-rfc2136-dynamic-updates).
*   **`bind_acl_policies`**: `{acl: {records: [host, ...] | any_name: true, record_types: [TXT], domain}}` — update rights every TSIG key in that ACL inherits (`fabricctl acl policy`); see [operations.md](operations.md#acl-update-policies-who-may-mint-certificates).

**Example DNS Configuration (`custom-vars.yaml`):**
```yaml
dns:
  dynamic_zone_var:
    zone_authority: true
    A:
    - { ip: "{{ host_ip }}", name: "{{ hostname }}" }
    - { ip: 192.168.1.10, name: server1 }
    AAAA:
    - { ip: "2001:db8::1", name: ipv6-host }
    CNAME:
    - { canonical: "{{ hostname }}", name: www }
    - { canonical: server1, name: ftp }
    MX:
    - { exchange: mail.example.com., priority: 10, name: "@" }
    TXT:
    - { text: "v=spf1 mx ~all", name: "@" }
    SRV:
    - { target: server1, port: 8080, priority: 10, weight: 5, name: _http._tcp }
```


## 3. PKI & Certificates (Step-CA)
These variables define how the internal Certificate Authority generates and signs certificates.

### `ca_name`
**Description:** The Common Name (CN) of the Root CA.

**Default Value:** `friendly_name` + `" CA"`

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `vars.yaml.j2`

### `cert_country`
**Description:** The country field (C) for the certificates.

**Default Value:** `"US"`

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `nginx/www/certs/index.html.j2`
- `stepca/leaf.tpl.j2`
- `stepca/subca.tpl.j2`
- `vars.yaml.j2`

### `cert_province`
**Description:** The state/province field (ST) for the certificates.

**Default Value:** `"State"`

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `nginx/www/certs/index.html.j2`
- `stepca/leaf.tpl.j2`
- `stepca/subca.tpl.j2`
- `vars.yaml.j2`

### `cert_city`
**Description:** The city/locality field (L) for the certificates.

**Default Value:** `"City"`

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `nginx/www/certs/index.html.j2`
- `stepca/leaf.tpl.j2`
- `stepca/subca.tpl.j2`
- `vars.yaml.j2`

### `cert_org`
**Description:** The organization field (O) for the certificates.

**Default Value:** `friendly_name`

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `nginx/www/certs/index.html.j2`
- `stepca/leaf.tpl.j2`
- `stepca/subca.tpl.j2`
- `vars.yaml.j2`

### `cert_ou`
**Description:** The organizational unit field (OU) for the certificates.

**Default Value:** `"IT"`

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `nginx/www/certs/index.html.j2`
- `stepca/leaf.tpl.j2`
- `stepca/subca.tpl.j2`
- `vars.yaml.j2`

### `cert_root_ca_days`
**Description:** The validity lifetime (in days) of the Root CA.

**Default Value:** `1825` (5 years)

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `nginx/www/certs/index.html.j2`
- `vars.yaml.j2`

### `cert_root_digest`
**Description:** The signature hash algorithm for the Root CA.

**Default Value:** `"sha512"`

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `vars.yaml.j2`

### `cert_root_key_type`
**Description:** The key type for the Root CA (e.g., rsa, ecdsa, ed25519).

**Default Value:** `"rsa"`

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `nginx/www/certs/index.html.j2`
- `vars.yaml.j2`

### `cert_root_key_param`
**Description:** The key parameter for the Root CA (e.g., 4096).

**Default Value:** `"4096"`

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `nginx/www/certs/index.html.j2`
- `vars.yaml.j2`

### `cert_intermediate_days`
**Description:** The validity lifetime (in days) of the Intermediate CA.

**Default Value:** `1095` (3 years)

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `nginx/www/certs/index.html.j2`
- `vars.yaml.j2`

### `cert_intermediate_digest`
**Description:** The signature hash algorithm for the Intermediate CA.

**Default Value:** `"sha512"`

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `vars.yaml.j2`

### `cert_intermediate_key_type`
**Description:** The key type for the Intermediate CA.

**Default Value:** `"rsa"`

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `nginx/www/certs/index.html.j2`
- `vars.yaml.j2`

### `cert_intermediate_key_param`
**Description:** The key parameter for the Intermediate CA.

**Default Value:** `"4096"`

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `nginx/www/certs/index.html.j2`
- `vars.yaml.j2`

### `cert_service_days`
**Description:** The maximum validity lifetime (in days) of leaf certificates.

**Default Value:** `365` (1 year)

**Effected Jinja Templates:**
- `vars.yaml.j2`

### `pki_manual_max_days`
**Description:** The longest validity (in days) of a certificate issued by hand from the web UI's Step-CA tab — a signed CSR or a generated key pair. Requests above it are refused.

**Default Value:** `1825` (5 years)

**Effected Jinja Templates:**
- `vars.yaml.j2`

### `cert_acme_lifetime_hours`
**Description:** The default validity of certificates requested via ACME.

**Default Value:** `"720h"` (30 days)

**Effected Jinja Templates:**
- `nginx/www/certs/index.html.j2`
- `vars.yaml.j2`

### `stepca_port`
**Description:** The port Step-CA listens on.

**Default Value:** `9000`

**Effected Jinja Templates:**
- `nginx/nginx.conf.j2`
- `stepca/docker-compose.yml.j2`
- `vars.yaml.j2`

### `stepca_cert_allow_subordinate_ca`
**Description:** Whether Step-CA allows signing subordinate CA certs.

**Default Value:** `true`

**Effected Jinja Templates:**
- `vars.yaml.j2`

### `stepca_cert_max_lifetime_hours`
**Description:** The max lifetime Step-CA will issue a certificate for.

**Default Value:** `cert_service_days * 24h`

**Effected Jinja Templates:**
- `vars.yaml.j2`


### Bring Your Own Certificates (BYOC)
If you already possess a securely offline-generated Root and Intermediate CA, you can import them instead of letting Step-CA mint its own.

### `byoc`
**Description:** Set to `true` to enable importing your own CAs.

**Default Value:** `false`

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `vars.yaml.j2`

### `ca_crt_path`
**Description:** Absolute path to your existing Root CA certificate.

**Default Value:** `"/home/default_admin/output/root_ca.crt"`

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `vars.yaml.j2`

### `ica_crt_path`
**Description:** Absolute path to your existing Intermediate CA certificate.

**Default Value:** `"/home/default_admin/output/ica.crt"`

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `vars.yaml.j2`

### `ica_key_path`
**Description:** Absolute path to your existing Intermediate CA private key.

**Default Value:** *(None)*

**Immutable:** Yes 🔒


## 4. Docker Infrastructure
Allows deep customization of the container orchestration, including overriding images and statically assigning internal IPs on the Docker bridge.

### General Orchestration
### `compose_file`
**Description:** Path to the generated `docker-compose.yml` file.

**Default Value:** `deploy_base_dir` + `"/fabric/docker-compose.yml"`

**Effected Jinja Templates:**
- `vars.yaml.j2`

### `project_containers`
**Description:** List of containers to include in deployment.

**Default Value:** `['nginx', 'step-ca', 'bind9']` plus `dirsrv` (if `install_ldap`), `keycloak`, `postgres` (if `install_keycloak`) and `webui` (if `install_webui` and `install_keycloak`). The optional entries are re-derived from the `install_*` flags on every render.

**Effected Jinja Templates:**
- `vars.yaml.j2`

### `nginx_backend_ldap`
**Description:** Upstream for the nginx stream listener on port 389 (plain TCP passthrough; 389-DS requires StartTLS).

**Default Value:** `"dirsrv:3389"`

**Effected Jinja Templates:**
- `nginx/nginx.conf.j2`
- `vars.yaml.j2`

### `nginx_backend_ldaps`
**Description:** Upstream for the nginx stream listener on port 636 (plain TCP passthrough; 389-DS terminates LDAPS itself).

**Default Value:** `"dirsrv:3636"`

**Effected Jinja Templates:**
- `nginx/nginx.conf.j2`
- `vars.yaml.j2`

### `nginx_backend_stepca`
**Description:** Upstream target for Nginx Step-CA proxy.

**Default Value:** `"https://step-ca:9000"`

**Effected Jinja Templates:**
- `nginx/nginx.conf.j2`
- `vars.yaml.j2`

### `keycloak_data_dir`
**Description:** Directory where Keycloak persists its data.

**Default Value:** `deploy_base_dir` + `"/keycloak/data"`

**Effected Jinja Templates:**
- `keycloak/docker-compose.yml.j2`
- `vars.yaml.j2`

### `postgres_data_dir`
**Description:** Directory where the Postgres database persists its data.

**Default Value:** `deploy_base_dir` + `"/postgres/data"`

**Effected Jinja Templates:**
- `postgres/docker-compose.yml.j2`
- `vars.yaml.j2`

### `host_ram_capacity`
**Description:** Host RAM limit in GB (min 3) to enforce memory ceilings and staggered boots. `0` disables limits. At 3/4 GB the 389-DS container is limited to `256M`/`384M` (with `DS_MEMORY_PERCENTAGE=10`).

**Default Value:** `0`


### Internal IP Assignments
| Variable | Default Value |
|----------|---------------|
| `ip_nginx` | `"10.255.0.10"` |
| `ip_bind9` | `"10.255.0.30"` |
| `ip_stepca` | `"10.255.0.40"` |
| `ip_ldap` | `"10.255.0.50"` |
| `ip_keycloak` | `"10.255.0.60"` |
| `ip_postgres` | `"10.255.0.70"` |
| `ip_webui` | `"10.255.0.80"` (webui container; on `fabric_net` only to reach Keycloak, no published ports) |

### Container Images
| Variable | Default Value |
|----------|---------------|
| `image_nginx` | `"nginx:latest"` |
| `image_bind9` | `"ubuntu/bind9:latest"` — base of the local hardened layer `fabric/bind9:local` (`fabric/jinja/bind9/build`) |
| `image_stepca` | `"smallstep/step-ca:latest"` |
| `image_dirsrv`| `"fabric/dirsrv:local"` (built locally from `fabric/jinja/dirsrv/build`, Debian stable + `389-ds-base`) |
| `image_keycloak`| `"keycloak/keycloak:latest"` — base of the local pre-built layer `fabric/keycloak:local` (`fabric/jinja/keycloak/build`, `kc.sh build`, started with `start --optimized`) |
| `image_postgres`| `"postgres:latest"` |
| `image_webui`| `"fabric/webui:local"` (built locally from `fabric/jinja/webui/build`, `debian:trixie-slim` + `python3`, `python3-jinja2`, `openssl`, `tini`; app = `fabric/lib/webui`) |

**Upgrades:** re-running `fabricctl setup` on an existing install takes this release's default for every `image_*` key, except the ones you pinned: keys set in a `--file` or the checkout's `custom-vars.yaml` are recorded in `image_pins` and kept on every later run. To unpin, remove the key from `image_pins` in `/opt/fabric/config/vars.yaml`.

### Service CNAMEs
Allows overriding the default short hostnames (CNAMEs) automatically assigned to the services.
| Variable | Default Value |
|----------|---------------|
| `cname_ca` | `"ca"` |
| `landing_page_cname` | `""` (Empty string, defaults to root domain) |
| `cname_dns` | `"dns"` |
| `cname_ldap` | `"ldap"` |
| `cname_sso` | `"sso"` |
| `cname_mgr` | `"fabric"` (label of the default web UI name; CNAME added only when webui is enabled and it differs from `hostname`) |
| `cname_certs` | `"certs"` (CA certificate page) |
| `webui_hostname` | *(empty)* — any host name for the web UI; overrides `cname_mgr` |

### Internal Subdomain Routing (Nginx)
By default, the fully qualified hostnames are constructed using the CNAMEs above appended with the base `domain`.
| Variable | Default Value |
|----------|---------------|
| `hostname_nginx` | `"nginx." + domain` |
| `hostname_bind9` | `cname_dns + "." + domain` |
| `hostname_stepca` | `cname_ca + "." + domain` |
| `hostname_landing` | `landing_page_cname + "." + domain` (or `domain` if empty) |
| `hostname_ldap` | `cname_ldap + "." + domain` |
| `hostname_keycloak`| `cname_sso + "." + domain` |
| `hostname_mgr`| `webui_hostname`, else `cname_mgr + "." + domain` — computed on every render (webui vhost; `redirect_uri` is `https://<hostname_mgr>/oidc/callback`) |
| `hostname_certs`| `cname_certs + "." + domain` — CA certificates for every system (`ca.<domain>` is Step-CA's API) |

## 5. Security Contexts & Features
Toggle features and control system-level UNIX isolation mapping.

### `install_ldap`
**Description:** Toggles whether the 389 Directory Server (`dirsrv`) container and the nginx LDAP/LDAPS stream listeners are deployed.

**Default Value:** `true`

**Effected Jinja Templates:**
- `nginx/nginx.conf.j2`
- `vars.yaml.j2`

### `install_keycloak`
**Description:** Toggles whether Keycloak (and PostgreSQL) are deployed.

**Default Value:** `false`

**Effected Jinja Templates:**
- `nginx/nginx.conf.j2`
- `nginx/www/landing/index.html.j2`
- `vars.yaml.j2`

### `install_webui`
**Description:** Deploys the webui management UI (unprivileged container `webui` + privileged host service `fabric-agent`, nginx vhost `hostname_mgr`, `fabric` CNAME, service cert). Forced to `false` unless `install_keycloak` is `true`. See [webui.md](webui.md).

**Default Value:** `true` (effective only with Keycloak)

**Effected Jinja Templates:**
- `nginx/docker-compose.yml.j2`
- `nginx/nginx.conf.j2`
- `vars.yaml.j2`
- `webui/docker-compose.yml.j2`, `webui/webui.json.j2`, `systemd/fabric-agent.service.j2` (rendered only when enabled)

### webui Settings
| Variable | Default Value | Description |
|----------|---------------|-------------|
| `webui_realm` | `domain` | Keycloak realm used for login and created/configured by `keycloak_bootstrap.py` |
| `webui_admin_role` | `"fabric-admin"` | Realm role required to use webui |
| `webui_admin_group` | `"admins"` | LDAP/Keycloak group granted `webui_admin_role` |
| `webui_session_idle` | `900` | Session idle timeout (seconds) |
| `webui_session_max` | `28800` | Absolute session lifetime (seconds) |

`webui_realm`, `webui_admin_role` and `webui_admin_group` are rendered into `vars.yaml`; the session timeouts are read only by `webui/webui.json.j2` (set them in `custom-vars.yaml`). The OIDC client secret `webui_oidc_secret` is generated with fabric's secrets (OpenBao).

### `service_users`
**Description:** Dictionary mapping container names to UID/GID objects for setting permissions.

**Default Value:** *(See default configuration below)*

**Merge behaviour:** user entries are merged over the defaults (not a replacement), so a `vars.yaml` rendered by an older release still gains new accounts such as `webui`.

**Effected Jinja Templates:**
- `bind9/docker-compose.yml.j2`
- `keycloak/docker-compose.yml.j2`
- `nginx/docker-compose.yml.j2`
- `nginx/nginx.conf.j2`
- `postgres/docker-compose.yml.j2`
- `stepca/docker-compose.yml.j2`
- `systemd/fabric-agent.service.j2`
- `webui/docker-compose.yml.j2`
- `webui/webui.json.j2`
- `vars.yaml.j2`

### `service_dirs`
**Description:** List defining data directories and their owning users to create.

**Default Value:** *(See default configuration below)*

**Effected Jinja Templates:**
- `vars.yaml.j2`


### Default Security Contexts

**`service_users` Default:**
```yaml
service_users:
  bind:     { uid: 53,  gid: 53 }
  ldap:     { uid: 911, gid: 911 }
  nginx:    { uid: 443, gid: 443 }
  step:     { uid: 135, gid: 135 }
  keycloak: { uid: 900, gid: 0 }
  postgres: { uid: 901, gid: 901 }
  webui:    { uid: 912, gid: 912 }   # webui container user; also the fabric-agent socket group
```

**`service_dirs` Default:**
```yaml
service_dirs:
  - { folder: nginx,    owner: nginx }
  - { folder: bind9,    owner: bind }
  - { folder: stepca,   owner: step }
  - { folder: dirsrv,   owner: ldap }
  - { folder: keycloak, owner: keycloak }
  - { folder: postgres, owner: postgres }
  - { folder: webui,  owner: root }
```
Built-in folders always come from these defaults; user-added folders are kept.

### OpenBao (core)

| Variable | Default | What |
|---|---|---|
| `image_openbao` | `openbao/openbao:2.7.0@sha256:71156a1c…` | Pinned by tag **and** digest (amd64 + arm64) |
| `ip_openbao` | `10.255.0.90` | Address on fabric_net |
| `cname_openbao` / `hostname_openbao` | `vault` / `vault.<domain>` | Published through nginx; CNAME added to the zone |
| `openbao_key_dir` | `/etc/fabric/openbao` | Unlock methods (`slots.json`, key-file method `local-<id>.key`) and AppRole credentials — all root-only |
| `openbao_runtime_dir` | `/run/fabric/openbao` | RAM folder fabric-unlock hands the vault key through at start (wiped once unsealed) |
| `openbao_seal_key_id` | `fabric-1` | First vault key id (later ids come from `fabricctl vault rotate`) |
| `openbao_recovery_shares` / `openbao_recovery_threshold` | `1` / `1` | Recovery keys created at the first init |
| `openbao_mem_limit` | `256m` | Container memory limit |

## 6. 389 Directory Server (LDAP) Specifics
If `install_ldap` is enabled, these settings govern the directory structure and policy. Seed LDIFs live in `fabric/jinja/dirsrv/seed/` and are applied idempotently (entries are only added when missing), so changing these after install adds new OUs/groups but never deletes existing ones.

### `ldap_base_dn`
**Description:** Base distinguished name (389-DS suffix), automatically computed from `domain`.

**Default Value:** `dc=lan,dc=example,dc=com`

**Effected Jinja Templates:**
- `dirsrv/docker-compose.yml.j2`
- `dirsrv/seed/10-tree.ldif.j2`
- `dirsrv/seed/20-accounts.ldif.j2`
- `dirsrv/seed/30-aci.ldif.j2`

### `ldap_groups`
**Description:** Defines the security groups to pre-provision in LDAP (created as `groupOfNames` + `posixGroup` under `ou=groups`).

**Default Value:** `[{name: admins, gidNumber: 1100, permissions: [read, write, modify]}, ...]`

**Effected Jinja Templates:**
- `dirsrv/seed/10-tree.ldif.j2`
- `vars.yaml.j2`

### `ldap_organizational_units`
**Description:** Defines the tree structure/OUs to pre-provision.

**Default Value:** `[{name: accounts, description: User Accounts}, ...]`

**Effected Jinja Templates:**
- `dirsrv/seed/10-tree.ldif.j2`
- `vars.yaml.j2`

### Directory Policy
| Variable | Default Value | Template |
|----------|---------------|----------|
| `ldap_password_min_length` | `12` | `dirsrv/seed/00-config.ldif.j2` |
| `ldap_lockout_max_failures` | `5` | `dirsrv/seed/00-config.ldif.j2` |
| `ldap_lockout_duration` | `900` (seconds) | `dirsrv/seed/00-config.ldif.j2` |
| `dirsrv_errorlog_level` | `8192` | `dirsrv/docker-compose.yml.j2` |

### Role Accounts
Created under `ou=admins,ou=accounts,<base_dn>` by `dirsrv/seed/20-accounts.ldif.j2`, each with its own password generated with fabric's secrets (OpenBao; `fabricctl secrets show <name>`; there is no shared default password):

| Account | Secret |
|---------|--------|
| `cn=super_admin` | `ldap_super_admin_password` |
| `cn=group_admin` | `ldap_group_admin_password` |
| `cn=user_creator_admin` | `ldap_user_creator_password` |
| `cn=user_modifier_admin` | `ldap_user_modifier_password` |
| `cn=keycloak_admin` | `ldap_keycloak_password` |
| `cn=device_admin` | `ldap_device_admin_password` — used by fabric-agent for the web UI's devices and device roles; may change only `ou=devices` and `ou=device-roles` |

`cn=Directory Manager` uses `ldap_admin_password`.


**Example LDAP Configuration (`custom-vars.yaml`):**
```yaml
ldap_groups:
- { gidNumber: 1100, name: admins, permissions: [read, write, modify] }
- { gidNumber: 1200, name: developers, permissions: [read, write] }
- { gidNumber: 1300, name: operations, permissions: [read, write] }
- { gidNumber: 5000, name: users, permissions: [read] }

ldap_organizational_units:
- { name: accounts, description: User Accounts }
- { name: groups, description: Security Groups }
- { name: admins, description: Privileged accounts, parent: accounts, uid_range: 1101-1999 }
- { name: users, description: Regular User accounts, parent: accounts, uid_range: 5001-50000 }
- { name: hosts, description: Computer objects, uid_range: 2000-4900 }
- { name: services, description: Service Accounts }
```

## 7. Landing Page Links (`link-vars.yaml`)
The `link-vars.yaml` file (or `link-vars-template.yaml`) defines the dynamic list of quick links shown on the Fabric Landing Portal. It is managed interactively via `fabricctl` under the **Landing Page Links** menu.

### `links`
**Description:** A list of dictionaries containing `name` and `link` keys for each quick link to display on the landing page. The `link` values can use Jinja variables like `{{ domain }}` or `{{ hostname_keycloak }}` which will be evaluated natively during deployment.

**Default Value:**
```yaml
links:
  - name: Keycloak (Admin)
    link: "sso.{{ domain }}/admin"
```

**Effected Jinja Templates:**
- `nginx/www/landing/index.html.j2`
