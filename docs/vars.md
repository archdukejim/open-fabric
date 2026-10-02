# fabric Configuration Variables

This document details all available configuration variables that can be defined in your `custom-vars.yaml` file. 

The `custom-vars.yaml` file acts as the single source of truth for rendering the infrastructure environment. While only a handful of variables are required (and included in the default `fabricctl/examples/vars.yaml`), you may optionally define any of the variables below to override the backend system defaults.

Every setting and its default is defined in `fabricctl/jinja/vars.yaml.j2`, which is rendered into `vars.yaml` on every apply. **Immutable** settings are ones the interactive `fabricctl` menu refuses to change after install (they are baked into the CA or the file layout); most of them only take effect when Step-CA is first initialised.

---

## 1. Global Options
These variables define top-level identity and basic settings.

### `domain`
**Description:** The base domain for the local network (e.g. `lan.example.com`). **Required.**

**Default Value:** *(Mandatory - Template: `example.com`; `fabricctl setup` suggests `home.arpa` when it is missing)*

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `bind9/config/named.conf.zones.j2`
- `bind9/data/reverse-zone.j2`
- `bind9/data/zone.j2`
- `dirsrv/seed/10-tree.ldif.j2`
- `kea/docker-compose.yml.j2`, `kea/kea-dhcp4.conf.j2`, `kea/kea-dhcp-ddns.conf.j2`
- `nginx/nginx.conf.j2`
- `nginx/www/certs/index.html.j2`
- `nginx/www/certs/install-certs.sh.j2`
- `nginx/www/ldap/index.html.j2`, `nginx/www/ldap/install-ldap.sh.j2`
- `vars.yaml.j2` (every `hostname_*`, `ldap_base_dn`, `webui_realm`)

### `domain_file`
**Description:** The domain name formatted for use as a filename (dots replaced with underscores).

**Default Value:** `domain` with `.` replaced by `_`

**Effected Jinja Templates:**
- `nginx/nginx.conf.j2`
- `nginx/www/certs/index.html.j2`
- `nginx/www/certs/install-*.sh.j2` (all five install scripts)
- `nginx/www/ldap/index.html.j2`, `nginx/www/ldap/install-ldap.sh.j2`
- `vars.yaml.j2`

### `hostname`
**Description:** The hostname of the Docker host server: a single label, no dots. It gets an A record (`host_ip`) in the zone and is the target of every service CNAME. **Required.**

**Default Value:** *(Mandatory - Template: `fabric`)*

**Effected Jinja Templates:**
- `fluentbit/fluent-bit.yaml.j2` (the `fabric_host` field on forwarded records)
- `vars.yaml.j2` (default A and CNAME records in `dns`)

### `friendly_name`
**Description:** A friendly display name for organizations or the CA. Also the default of `ca_name` and `cert_org`.

**Default Value:** `"Example Org"` (`fabricctl setup` asks for it, suggesting `"Home Network"`, when it is empty)

**Effected Jinja Templates:**
- `nginx/www/certs/index.html.j2`
- `nginx/www/certs/install-certs.sh.j2`
- `nginx/www/certs/install-chrome-ubuntu.sh.j2`
- `nginx/www/certs/install-firefox-ubuntu.sh.j2`
- `nginx/www/certs/install-python-ubuntu.sh.j2`
- `nginx/www/landing/index.html.j2`
- `nginx/www/ldap/index.html.j2`
- `nginx/www/manual/index.html.j2`
- `nginx/www/shared/base.html.j2`
- `vars.yaml.j2`

The footer settings below are all read by `nginx/www/shared/base.html.j2` (the footer of every nginx web page). Their default is empty (rendered as `null`); an empty value is not shown.

### `service_mark`
**Description:** Text to display with the Service Mark (`℠`) symbol in the footer.

**Default Value:** *(empty)*

### `trademark`
**Description:** Text to display with the Trademark (`™`) symbol in the footer.

**Default Value:** *(empty)*

### `copyright`
**Description:** Copyright holder/year to display with the Copyright (`©`) symbol in the footer.

**Default Value:** *(empty)*

### `contact_email`
**Description:** Contact email address displayed in the footer.

**Default Value:** *(empty)*

### `contact_phone`
**Description:** Contact phone number displayed in the footer.

**Default Value:** *(empty)*

### `address_line1`
**Description:** Primary address line displayed in the footer.

**Default Value:** *(empty)*

### `address_line2`
**Description:** Secondary address line (e.g., Suite, City, State) displayed in the footer.

**Default Value:** *(empty)*

### `care_of`
**Description:** Attribution text displayed with the Care Of (`℅`) symbol in the footer.

**Default Value:** *(empty)*

### `system_timezone`
**Description:** Intended as the timezone for the server/containers. **Not applied:** it is rendered into `vars.yaml`, but no template or code reads it; containers and the host keep their own timezone.

**Default Value:** `"America/New_York"`

**Effected Jinja Templates:**
- `vars.yaml.j2`

### `deploy_base_dir`
**Description:** The base directory on the host where project data and configs will be deployed. `fabricctl setup` overwrites it with the install base it runs against on every run.

**Default Value:** `"/opt"`

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- every `<service>/docker-compose.yml.j2` (bind9, dirsrv, fluentbit, freeradius, kea, keycloak, nginx, openbao, postgres, stepca, webui)
- `systemd/fabric-agent.service.j2`
- `systemd/wrapper.service.j2`
- `vars.yaml.j2` (`compose_file`, `keycloak_data_dir`, `postgres_data_dir`)

## 2. Networking & DNS
> [!WARNING]
> Editing core networking configurations post-deployment can impact routing and require widespread service restarts. Proceed with caution.

These settings dictate how containers route traffic and how the BIND9 DNS server handles resolution.

### `host_ip`
**Description:** The primary IP address of the Docker host (IPv4). Published ports bind to it, and it is the address of `hostname` in the zone. **Required.**

**Default Value:** *(Mandatory - Template: `192.168.1.100`)*

**Effected Jinja Templates:**
- `bind9/data/zone.j2`
- `bind9/docker-compose.yml.j2`
- `freeradius/docker-compose.yml.j2`
- `kea/kea-dhcp4.conf.j2` (default DNS server handed to clients)
- `nginx/docker-compose.yml.j2`
- `nginx/nginx.conf.j2`
- `nginx/www/certs/index.html.j2`
- `vars.yaml.j2`

### `lan_cidr`
**Description:** The subnet representing your local LAN clients (IPv4 network). It is in the `dns-resolvers` ACL, it is the network the host firewall allows (SSH and Docker-published ports; see `security`), and the default DHCP subnet offered by `fabricctl setup`. **Required.**

**Default Value:** *(Mandatory - Template: `192.168.1.0/24`)*

**Effected Jinja Templates:**
- `vars.yaml.j2` (`bind_acls`)
- read by `fabriclib/setup/configure_firewall.py`, `fabriclib/security/apply_docker_firewall.py`, `fabriclib/dns/builtin_acls.py`

### `lan_gateway`
**Description:** The default gateway router IP for your LAN (IPv4). Used only as the default router when `fabricctl setup` asks for the DHCP subnet. **Required.**

**Default Value:** *(Mandatory - Template: `192.168.1.1`)*

**Effected Jinja Templates:**
- `vars.yaml.j2`
- read by `fabriclib/setup/choose_plan.py`

### `fabric_subnet`
**Description:** The internal Docker bridge subnet for the fabric services (`fabric_net`, created by setup; an existing network is not changed). It is in the `acme-updaters` and `dns-resolvers` ACLs, and the fabric-agent service and OpenBao accept connections from it. The `ip_*` addresses must lie inside it.

**Default Value:** `10.255.0.0/24`

**Effected Jinja Templates:**
- `systemd/fabric-agent.service.j2`
- `vars.yaml.j2` (`bind_acls`)
- read by `fabriclib/setup/configure_network.py`, `fabriclib/vault/configure_openbao.py`

### `use_host_dns`
**Description:** If `true`, the host's resolver is left as it is. If `false`, setup writes a systemd-resolved drop-in that uses `dns_server` with the stub listener off (this frees port 53 on the host) and points `/etc/resolv.conf` at it.

**Default Value:** `true`

**Effected Jinja Templates:**
- `vars.yaml.j2`
- read by `fabriclib/setup/configure_network.py`

### `dns_server`
**Description:** Upstream DNS server for the **host's** resolver, used only when `use_host_dns` is `false`. BIND9 does not forward to it (BIND9 is authoritative only, `recursion no`).

**Default Value:** `"8.8.8.8"`

**Effected Jinja Templates:**
- `vars.yaml.j2`
- read by `fabriclib/setup/configure_network.py`

### `bind_dns_port`
**Description:** The host port (on `host_ip`, UDP and TCP) published to BIND9's port 53. Also the port given to RFC2136 clients in TSIG key settings, and checked by setup's final verification. A federation site reports it when it joins, and linked sites send zone transfers and NOTIFYs there. Set it when another resolver owns port 53 on the host, e.g. AdGuard Home in front of BIND (clients ask AdGuard on 53, AdGuard forwards your domain to BIND on 5053): DHCP can hand out only an address, never a port, so the resolver clients use must be on 53.

**Default Value:** `53`

**Effected Jinja Templates:**
- `bind9/docker-compose.yml.j2`
- `vars.yaml.j2`
- read by `fabriclib/dns/rfc2136_settings.py`, `fabriclib/setup/verify_install.py`

### `bind9_doh_port`
**Description:** The port BIND9 listens on for DNS-over-HTTPS inside `fabric_net` (plain HTTP; nginx terminates TLS on `hostname_bind9` and proxies to it). Not published on the host.

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
**Description:** The name of the CA: passed to `step ca init --name` at the first Step-CA initialisation (Step-CA derives the root and intermediate CNs from it), and shown on the web pages.

**Default Value:** `friendly_name` + `" CA"`

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `nginx/www/certs/index.html.j2`, `nginx/www/certs/install-{chrome,firefox,python}-ubuntu.sh.j2`
- `nginx/www/landing/index.html.j2`, `nginx/www/ldap/index.html.j2`, `nginx/www/manual/index.html.j2`, `nginx/www/shared/base.html.j2`
- `vars.yaml.j2`
- read by `fabriclib/setup/init_pki.py`

The subject fields `cert_country`, `cert_province`, `cert_city`, `cert_org` and `cert_ou` go into the Step-CA certificate templates (`leaf.tpl`, `subca.tpl`), which are used for ACME certificates, CSRs signed from the web UI, and key pairs or sub-CAs minted by fabric. Setup's own service certificates are issued without a template. The templates are re-rendered on every apply, so a change affects new certificates only.

### `cert_country`
**Description:** The country field (C) for the certificates.

**Default Value:** `"US"`

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `stepca/leaf.tpl.j2`
- `stepca/subca.tpl.j2`
- `vars.yaml.j2`

### `cert_province`
**Description:** The state/province field (ST) for the certificates.

**Default Value:** `"State"`

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `stepca/leaf.tpl.j2`
- `stepca/subca.tpl.j2`
- `vars.yaml.j2`

### `cert_city`
**Description:** The city/locality field (L) for the certificates.

**Default Value:** `"City"`

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
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
- `stepca/leaf.tpl.j2`
- `stepca/subca.tpl.j2`
- `vars.yaml.j2`

### `cert_root_ca_days`
**Description:** Intended as the validity lifetime (in days) of the Root CA. **Not applied:** `step ca init` runs with Step-CA's own defaults; fabric does not pass this setting, and nothing else reads it.

**Default Value:** `1825` (5 years)

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `vars.yaml.j2`

### `cert_root_digest`
**Description:** Intended as the signature hash algorithm for the Root CA. **Not applied:** `step ca init` runs with Step-CA's own defaults; fabric does not pass this setting, and nothing else reads it.

**Default Value:** `"sha512"`

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `vars.yaml.j2`

### `cert_root_key_type`
**Description:** Intended as the key type for the Root CA (e.g., rsa, ecdsa, ed25519). **Not applied:** `step ca init` runs with Step-CA's own defaults; fabric does not pass this setting, and nothing else reads it.

**Default Value:** `"rsa"`

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `vars.yaml.j2`

### `cert_root_key_param`
**Description:** Intended as the key parameter for the Root CA (e.g., 4096). **Not applied:** `step ca init` runs with Step-CA's own defaults; fabric does not pass this setting, and nothing else reads it.

**Default Value:** `4096`

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `vars.yaml.j2`

### `cert_intermediate_days`
**Description:** Intended as the validity lifetime (in days) of the Intermediate CA. **Not applied:** `step ca init` runs with Step-CA's own defaults; fabric does not pass this setting, and nothing else reads it.

**Default Value:** `1095` (3 years)

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `vars.yaml.j2`

### `cert_intermediate_digest`
**Description:** Intended as the signature hash algorithm for the Intermediate CA. **Not applied:** `step ca init` runs with Step-CA's own defaults; fabric does not pass this setting, and nothing else reads it.

**Default Value:** `"sha512"`

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `vars.yaml.j2`

### `cert_intermediate_key_type`
**Description:** Intended as the key type for the Intermediate CA. **Not applied:** `step ca init` runs with Step-CA's own defaults; fabric does not pass this setting, and nothing else reads it.

**Default Value:** `"rsa"`

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `vars.yaml.j2`

### `cert_intermediate_key_param`
**Description:** Intended as the key parameter for the Intermediate CA. **Not applied:** `step ca init` runs with Step-CA's own defaults; fabric does not pass this setting, and nothing else reads it.

**Default Value:** `4096`

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `vars.yaml.j2`

### `cert_service_days`
**Description:** The validity (in days) of the service certificates `fabricctl setup` mints for nginx, BIND9, 389-DS and the other services, and the default of `stepca_cert_max_lifetime_hours`.

**Default Value:** `365` (1 year)

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `vars.yaml.j2` (`stepca_cert_max_lifetime_hours`)
- read by `fabriclib/pki/mint_cert.py`

### `pki_manual_max_days`
**Description:** The longest validity (in days) of a certificate issued by hand from the web UI's Step-CA tab — a signed CSR or a generated key pair. Requests above it are refused.

**Default Value:** `1825` (5 years)

**Effected Jinja Templates:**
- `vars.yaml.j2`
- read by `fabriclib/pki/common/valid_days.py`, `fabriclib/pki/ca_summary.py`

### `cert_acme_lifetime_hours`
**Description:** The default and maximum validity of certificates requested via ACME (the `acme` provisioner in Step-CA's `ca.json`). Written only at the first Step-CA initialisation.

**Default Value:** `"720h"` (30 days)

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `vars.yaml.j2`
- read by `fabriclib/setup/init_pki.py`

### `stepca_port`
**Description:** The port Step-CA listens on inside `fabric_net` (nginx publishes Step-CA as `hostname_stepca` on 443).

**Default Value:** `9000`

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `nginx/nginx.conf.j2`
- `stepca/docker-compose.yml.j2`
- `vars.yaml.j2`

### `stepca_cert_allow_subordinate_ca`
**Description:** Whether Step-CA's JWK provisioner may issue the basicConstraints extension, i.e. sign subordinate CA certificates. Written only at the first Step-CA initialisation.

**Default Value:** `true`

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `vars.yaml.j2`
- read by `fabriclib/setup/init_pki.py`

### `stepca_cert_max_lifetime_hours`
**Description:** The longest lifetime Step-CA will issue a certificate for (`maxTLSCertDuration` for the whole authority). Written only at the first Step-CA initialisation.

**Default Value:** `cert_service_days` × 24, in hours (`"8760h"`)

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `vars.yaml.j2`
- read by `fabriclib/setup/init_pki.py`


### Bring Your Own Certificates (BYOC)
If you already possess a securely offline-generated Root and Intermediate CA, you can import them instead of letting Step-CA mint its own.

### `byoc`
**Description:** Set to `true` to import your own root and intermediate at the first Step-CA initialisation (setup stops if any of the three files is missing). The intermediate key may be unencrypted or encrypted with fabric's `ca_password` (a federation site's is: [federation.md](design/federation.md)); Step-CA always gets its password file. The root key `step ca init` generated is removed, since it does not belong to your root.

**Default Value:** `false`

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `vars.yaml.j2`
- read by `fabriclib/setup/init_pki.py`

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
**Description:** Absolute path to your existing Intermediate CA private key. Only written to `vars.yaml` when set.

**Default Value:** *(None)* — then `ica_crt_path` with its extension replaced by `.key`

**Immutable:** Yes 🔒

### `ca_nest_depth`
**Description:** How many levels of federation sites may nest below a site (design [federation.md](design/federation.md) §6). Used once, when this install makes its own root CA: the root gets path length `ca_nest_depth + 1` (0 allows flat sites only, 1 lets a site invited with `--nest 1` hold sites of its own). 0..4. A brought-in root (`byoc`) has its own path length, which setup reports. Fixed once the root exists.

**Default Value:** `1`

**Immutable:** Yes 🔒

**Effected Jinja Templates:**
- `vars.yaml.j2`; read by `fabriclib/setup/init_pki.py`

### `ica_parents_path` / `site_ca_depth`
**Description:** Set by `fabricctl setup --join` (and `federation reparent`), not by hand: a nested site's parent CAs (the CA certificates between its intermediate and the root, copied to `stepca/data/certs/ca_parents.crt`) and how many there are. 0 for the root site and flat sites. Every certificate chain this site hands out carries the parents, and nginx's client-certificate depth for the web UI grows by `site_ca_depth`.

**Default Value:** unset / `0`

**Effected Jinja Templates:**
- `nginx/nginx.conf.j2` (`ssl_verify_depth`)
- `vars.yaml.j2`; read by `fabriclib/setup/init_pki.py`


## 4. Docker Infrastructure
Allows deep customization of the container orchestration, including overriding images and statically assigning internal IPs on the Docker bridge.

### General Orchestration
### `compose_file`
**Description:** Intended as the path of a combined `docker-compose.yml`. **Not used:** each service has its own compose file under `<deploy_base_dir>/<service>/`, and nothing reads this setting.

**Default Value:** `deploy_base_dir` + `"/fabric/docker-compose.yml"`

**Effected Jinja Templates:**
- `vars.yaml.j2`

### `project_containers`
**Description:** List of containers in the deployment. **Informational only:** it is rendered into `vars.yaml`, but nothing reads it; which services are deployed follows the `install_*` flags. It does not list `kea`, `freeradius` or `fluentbit`.

**Default Value:** `['nginx', 'step-ca', 'bind9', 'openbao']` plus `dirsrv` (if `install_ldap`), `keycloak`, `postgres` (if `install_keycloak`) and `fabric-web` (if `install_webui` and `install_keycloak`). The optional entries are re-derived from the `install_*` flags on every render, and `openbao` is always added.

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

**Default Value:** `"https://step-ca:"` + `stepca_port` (`"https://step-ca:9000"`)

**Effected Jinja Templates:**
- `nginx/nginx.conf.j2`
- `vars.yaml.j2`

### `keycloak_data_dir`
**Description:** Directory where Keycloak persists its data.

**Default Value:** `deploy_base_dir` + `"/keycloak/data"`

**Effected Jinja Templates:**
- `keycloak/docker-compose.yml.j2`
- `vars.yaml.j2`
- read by `deploy.py` (creates it), `fabriclib/setup/export_install.py`, `fabriclib/setup/uninstall.py`

### `postgres_data_dir`
**Description:** Directory where the Postgres database persists its data.

**Default Value:** `deploy_base_dir` + `"/postgres/data"`

**Effected Jinja Templates:**
- `postgres/docker-compose.yml.j2`
- `vars.yaml.j2`
- read by `deploy.py` (creates it), `fabriclib/setup/export_install.py`, `fabriclib/setup/uninstall.py`

### `host_ram_capacity`
**Description:** Host RAM in GB, used to set memory ceilings and staggered boots. `0` disables them; `1` and `2` are refused by apply (the minimum is 3). At 3/4 GB, for example, the 389-DS container is limited to `256M`/`384M` (with `DS_MEMORY_PERCENTAGE=10`). OpenBao, Kea, FreeRADIUS and Fluent Bit use their own `*_mem_limit` settings instead.

**Default Value:** `0`

**Effected Jinja Templates:**
- `bind9`, `dirsrv`, `keycloak`, `nginx`, `postgres`, `stepca` and `webui` `docker-compose.yml.j2`
- `systemd/wrapper.service.j2`
- read by `deploy.py` (validation)


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
| Variable | Default | Notes |
|---|---|---|
| `image_nginx` | validated `nginx:1.30.x@sha256:…` | from `fabricctl/images.lock.yaml` |
| `image_stepca` | validated `smallstep/step-ca:0.30.x@sha256:…` | base of `fabric/stepca:local` |
| `image_keycloak` | validated `keycloak/keycloak:26.x@sha256:…` | base of the pre-built layer `fabric/keycloak:local` (`kc.sh build`, `start --optimized`) |
| `image_postgres` | validated `postgres:18.x@sha256:…` | a new major is never automatic (data upgrade) |
| `image_debian` | validated `debian:trixie-slim@sha256:…` | base of `fabric/bind9:local` (BIND 9.20 from Debian packages), `fabric/dirsrv:local` (389-DS), `fabric/web:local`, `fabric/kea:local` and `fabric/freeradius:local` |
| `image_dirsrv`, `image_webui` | `fabric/dirsrv:local`, `fabric/web:local` | names of the locally built images |
| `image_kea` | `fabric/kea:local` | name of the locally built Kea image (optional DHCP) |
| `image_freeradius` | `fabric/freeradius:local` | name of the locally built FreeRADIUS image (optional 802.1X) |
| `image_fluentbit` | validated `fluent/fluent-bit:5.1.x@sha256:…` | optional log forwarding |
| `image_adguard` | validated `adguard/adguardhome:v0.107.x@sha256:…` | base of `fabric/adguard:local` (the same program without file capabilities); optional DNS filter |
| `image_oauth2proxy` | validated `quay.io/oauth2-proxy/oauth2-proxy:v7.15.x@sha256:…` | OIDC sign-in in front of AdGuard's UI |
| `image_pins` | `[]` | `image_*` keys the admin set explicitly; maintained by `fabricctl setup` |
| `image_prune` | `true` | after `fabricctl images update`, remove old images of fabric's repositories (never the rollback image or anything in use) |

**Every image is pinned by digest** (amd64 + arm64); the defaults come from
`fabricctl/images.lock.yaml`. **Upgrades never change running images:**
re-running `fabricctl setup` keeps the image each host runs;
`sudo fabricctl images update` moves it to the validated list (see
operations.md). Refs that are not pinned by digest (`nginx:latest`, from
older installs) are replaced once by the validated pin. Keys you set in a
`--file` or `custom-vars.yaml` are recorded in `image_pins`, kept, and
skipped by `images update` unless `--force`.

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
| `webui_hostname` | *(empty)* — any host name for the web UI; overrides `cname_mgr`. Outside `domain`, fabric issues its certificate but you point DNS at this host |

`cname_openbao` is listed under OpenBao below. `cname_radius` (default `"radius"`) can be set too, but it is not written to `vars.yaml`: it only builds `hostname_radius` (see 802.1X).

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

`hostname_certs`, `hostname_openbao`, `hostname_radius` and `hostname_mgr` are always computed from their CNAME settings (and `webui_hostname`); setting them directly has no effect. The other `hostname_*` values can be overridden.

## 5. Security Contexts & Features
Toggle features and control system-level UNIX isolation mapping.

### `security`
**Description:** Host hardening applied by `fabricctl setup`. A dictionary; the keys you set are merged over the defaults (unknown keys are kept). `fabricctl setup` lists each item in its plan and, under Advanced, states what turning it off costs.

| Key | Default | What it does |
|---|---|---|
| `firewall` | `true` | UFW: deny incoming, allow outgoing, SSH (22/tcp) only from `lan_cidr` and `firewall_allow` (existing UFW rules are kept); with `install_kea`, UDP 67 on each of `dhcp.interfaces`. Also rebuilds the `DOCKER-USER` iptables chain so Docker-published ports accept new connections only from the same networks (and, with `install_freeradius`, from the IPv4 `radius_clients` on UDP 1812/1813); `fabric-firewall.service` re-applies it at boot. Setup refuses to enable it when your SSH session comes from outside those networks. `false`: `DOCKER-USER` is opened, `fabric-firewall` disabled, UFW left as it is. |
| `firewall_allow` | `[]` | Extra source networks (CIDRs, e.g. a VPN) allowed next to `lan_cidr`. |
| `docker_daemon_hardening` | `true` | Merges into `/etc/docker/daemon.json`: `no-new-privileges`, no inter-container traffic on the default bridge (`icc: false`), no userland proxy, `live-restore`, `json-file` logs capped at 3 × 10 MB. Docker is restarted only when the file changed. `false`: nothing is written, but settings written earlier are not removed. |

**Default Value:** `{firewall: true, firewall_allow: [], docker_daemon_hardening: true}`

**Effected Jinja Templates:**
- `vars.yaml.j2`
- read by `fabriclib/setup/configure_firewall.py`, `fabriclib/security/apply_docker_firewall.py`, `fabriclib/setup/harden_docker.py`, `fabriclib/setup/choose_plan.py`

### `install_ldap`
**Description:** Toggles whether the 389 Directory Server (`dirsrv`) container and the nginx LDAP/LDAPS stream listeners are deployed. The first web UI admin and 802.1X (`install_freeradius`) need it.

**Default Value:** `true`

**Effected Jinja Templates:**
- `nginx/nginx.conf.j2`
- `dirsrv/*` (rendered only when enabled)
- `vars.yaml.j2`

### `install_keycloak`
**Description:** Toggles whether Keycloak (and PostgreSQL) are deployed. The web UI needs it.

**Default Value:** `false` in `vars.yaml.j2`; `fabricctl setup` treats a missing value as `true` and writes that into the settings.

**Effected Jinja Templates:**
- `nginx/nginx.conf.j2`
- `openbao/docker-compose.yml.j2`
- `vars.yaml.j2`

### `install_webui`
**Description:** Deploys the webui management UI (unprivileged container `fabric-web`, shown as "Open Fabric — web control", + privileged host service `fabric-agent`, nginx vhost `hostname_mgr`, `fabric` CNAME, service cert). Forced to `false` unless `install_keycloak` is `true`. See [webui.md](webui.md).

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
| `webui_admin_group` | `"admins"` | LDAP/Keycloak group granted `webui_admin_role`; the first admin is put in it |
| `webui_admin_user` | `"fabricadmin"` | Username of the first web UI admin, created by `fabricctl setup` in 389-DS with a client certificate (kit in `~/fabric-admin` of the user who ran setup). Setup chooses it once: the `sudo` user's name if valid, else `fabricadmin`; `admin` and `root` are refused |
| `webui_admin_email` | *(empty)* → `<webui_admin_user>@<domain>` | Email address of that first admin |
| `webui_client_cert_days` | `365` | Validity (days) of the first admin's client certificate |
| `webui_session_idle` | `900` | Session idle timeout (seconds) |
| `webui_session_max` | `28800` | Absolute session lifetime (seconds) |

`webui_realm`, `webui_admin_role`, `webui_admin_group`, `webui_admin_user`, `webui_admin_email` and `webui_client_cert_days` are rendered into `vars.yaml` (the last three are read by `fabriclib/setup/create_admin.py`); the session timeouts are read only by `webui/webui.json.j2` (set them in `custom-vars.yaml`). The OIDC client secret `webui_oidc_secret` is generated with fabric's secrets (OpenBao).

### `service_users`
**Description:** Dictionary mapping container names to UID/GID objects for setting permissions.

**Default Value:** *(See default configuration below)*

**Merge behaviour:** user entries are merged over the defaults (not a replacement), so a `vars.yaml` rendered by an older release still gains new accounts such as `webui`.

**Effected Jinja Templates:**
- every `<service>/docker-compose.yml.j2` (bind9, dirsrv, fluentbit, freeradius, kea, keycloak, nginx, openbao, postgres, stepca, webui)
- `nginx/nginx.conf.j2`
- `systemd/fabric-agent.service.j2`
- `webui/docker-compose.yml.j2`
- `webui/webui.json.j2`
- `vars.yaml.j2`

### `service_dirs`
**Description:** List of data directories and their owning users. **Informational only:** it is rendered into `vars.yaml`, but nothing reads it; `deploy.py` creates each service's folders itself.

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
  openbao:    { uid: 913, gid: 913 }
  fluentbit:  { uid: 914, gid: 914 }
  kea:        { uid: 915, gid: 915 }
  freeradius: { uid: 916, gid: 916 }
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
  - { folder: webui,    owner: root }
  - { folder: openbao,  owner: openbao }
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
| `openbao_admin_dir` | `/run/fabric/openbao-admin` | RAM folder with OpenBao's break-glass socket (generate-root), root and the openbao user only |
| `openbao_seal_key_id` | `fabric-1` | First vault key id (later ids come from `fabricctl vault rotate`) |
| `openbao_recovery_shares` / `openbao_recovery_threshold` | `1` / `1` | Recovery keys created at the first init |
| `openbao_mem_limit` | `256m` | Container memory limit |
| `openbao_pkcs11_modules` | `[]` → ykcs11, OpenSC, SoftHSM2 at their Debian/Ubuntu paths | PKCS#11 libraries (paths or globs) fabric may load for security-key unlock methods. They run as root: list only libraries you trust |

## 6. 389 Directory Server (LDAP) Specifics
If `install_ldap` is enabled, these settings govern the directory structure and policy. Seed LDIFs live in `fabricctl/jinja/dirsrv/seed/` and are applied idempotently (entries are only added when missing), so changing these after install adds new OUs/groups but never deletes existing ones.

### `ldap_base_dn`
**Description:** Base distinguished name of the organisation (389-DS): people, groups and device roles, with each site's part beneath it (`ldap_local_dn`). Choose it when the root site is installed, e.g. `ldap_base_dn: dc=lan` — `dc=` or `o=` first, then any `dc=` parts, lower case; it is a directory name only (the DNS domain stays a multi-label name). A site that joins an upstream gets the upstream's. Fixed at install: setup refuses to change it on a live install (marker `config/.ldap-base-dn`).

**Default Value:** one `dc=` per label of `org_domain`, e.g. `dc=lan,dc=example,dc=com` for `lan.example.com`

**Effected Jinja Templates:**
- `dirsrv/docker-compose.yml.j2`
- `dirsrv/seed/10-tree.ldif.j2`
- `dirsrv/seed/20-accounts.ldif.j2`
- `dirsrv/seed/30-aci.ldif.j2`
- `freeradius/config/fabric-radius.json.j2`
- `nginx/www/ldap/index.html.j2`, `nginx/www/ldap/install-ldap.sh.j2`

### `site_name`
**Description:** This install's site name (design [federation.md](design/federation.md)): names its part of the directory, `ou=<site_name>,<ldap_base_dn>`. One host-name label, lower-cased, and not the name of one of the organisation's top-level OUs (`accounts`, `groups`, `hosts`, `device-roles`, …), which sit beside it. Fixed at install: setup refuses to change it on a live install (marker `config/.site-name`).

**Default Value:** `hostname`

**Effected Jinja Templates:**
- `vars.yaml.j2` (`ldap_local_dn`)

### `ldap_local_dn`
**Description:** This site's part of the directory: a second 389-DS backend (`sitelocal`), a sub-suffix under the organisation, holding what belongs to this site only: its service accounts (`ou=admins`) and its devices (`ou=devices`). Always computed (it cannot be set). A search from `ldap_base_dn` finds both. Installs from before the split are moved on upgrade (`fabriclib/ldap/migrate_local_suffix.py`).

**Default Value:** `ou=<site_name>,<ldap_base_dn>`, e.g. `ou=lab,dc=lan`

**Effected Jinja Templates:**
- `dirsrv/docker-compose.yml.j2` (`DS_LOCAL_SUFFIX`)
- `dirsrv/seed/10-tree.ldif.j2`, `dirsrv/seed/20-accounts.ldif.j2`, `dirsrv/seed/30-aci.ldif.j2`
- `freeradius/config/fabric-radius.json.j2`

### `org_domain`
**Description:** The organisation's domain: names the organisation suffix (`ldap_base_dn`) and is shared by every site of a fabric (design [federation.md](design/federation.md)). A standalone install's is its own `domain`; a site that joined an upstream (`fabricctl setup --join`) gets the upstream's. Fixed at install: setup refuses to change it on a live install (marker `config/.org-domain`).

**Default Value:** `domain`

**Effected Jinja Templates:**
- `vars.yaml.j2` (the default `ldap_base_dn`)

### `federation_endpoint`
**Description:** Run the federation endpoint other sites join through: the `fabric-federation` service (unix socket), an nginx vhost at `hostname_federation` (join route rate- and size-limited), its certificate and a CNAME. Turn it on and off with `fabricctl federation enable|disable` (which also issues the certificate). Off: no new site can join; sites that joined stay.

**Default Value:** `false`

**Effected Jinja Templates:**
- `nginx/nginx.conf.j2`, `nginx/docker-compose.yml.j2` (socket mount)
- `systemd/fabric-federation.service.j2`
- `vars.yaml.j2` (the CNAME)

### `hostname_federation`
**Description:** The endpoint's name, always computed: `cname_federation` (default `federation`; it can be set but is not written to `vars.yaml`) + `.` + `domain`. An invitation carries it; joining sites connect by address and check this name on the certificate.

**Default Value:** `federation.<domain>`

**Effected Jinja Templates:**
- `nginx/nginx.conf.j2`
- `vars.yaml.j2`

### `ldap_groups`
**Description:** Defines the security groups to pre-provision in LDAP (created as `groupOfNames` + `posixGroup` under `ou=groups`).

**Default Value:** `[{name: admins, gidNumber: 1100, permissions: [read, write, modify]}, ...]`

Defaults also include one group per fabric role bundle (design D19): `auditors`,
`network-operators`, `equipment-operators`, `pki-operators`, `helpdesk`. A
group with a `bundle:` key has that Keycloak composite role granted to it
(`keycloak_bootstrap.py`); add people to the group to give them the bundle.
The defaults also include `network-staff` (1120) and `network-guests` (1121),
the groups `radius_people` lets join by password (802.1X).

Your entries are merged with the defaults by `name`: an entry with a default's
name replaces it, and defaults cannot be removed.

**Effected Jinja Templates:**
- `dirsrv/seed/10-tree.ldif.j2`
- `vars.yaml.j2`
- `keycloak_bootstrap.py` (bundle grants)

### `ldap_organizational_units`
**Description:** Defines the tree structure/OUs to pre-provision. Merged with the defaults by `name`, like `ldap_groups`.

**Default Value:** `[{name: accounts, description: User Accounts}, ...]` — `accounts`, `groups`, `users` (under `accounts`), `hosts` and `device-roles` (fabric device RBAC). `admins` and `devices` are not organisation OUs: they live in the local suffix (`ldap_local_dn`), and an entry with either name is dropped

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
Created under `ou=admins,<ldap_local_dn>` (this install's local suffix) by `dirsrv/seed/20-accounts.ldif.j2`, each with its own password generated with fabric's secrets (OpenBao; `fabricctl secrets show <name>`; there is no shared default password):

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
The `link-vars.yaml` file (`<deploy_base_dir>/fabric/config/link-vars.yaml`; until it exists, the shipped `fabricctl/link-vars-template.yaml`) defines the dynamic list of quick links shown on the landing portal. It is managed interactively via `fabricctl` under the **Landing Page Links** menu.

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

### Log forwarding (optional)
| Variable | Default | Notes |
|---|---|---|
| `install_fluentbit` | `false` | Fluent Bit forwards the journal and OpenBao's audit log (operations.md → Log forwarding) |
| `log_forwarding` | `{}` | `syslog: {host, port 6514, tls true, ca_file}`, `elastic: {url, user, index, ca_file}`, `hosts: {name: address}`, `buffer_limit: 256M` |
| `ip_fluentbit` | `10.255.0.95` | On fabric_net (metrics for `fabricctl logs status`) |
| `fluentbit_mem_limit` | `64m` | Container memory limit |

The Elasticsearch password is not a setting: `sudo fabricctl logs set-password elastic` keeps it in OpenBao.

### DNS filter (optional: AdGuard Home)
Design [dns-filter.md](design/dns-filter.md); operations.md → DNS filter.

| Variable | Default | Notes |
|---|---|---|
| `dns_filter` | `none` | `adguard`: AdGuard Home answers clients on `host_ip:53` and BIND moves to `bind_dns_port` 5053. Out of the box AdGuard points at local DNS only (this site's BIND); set up its internet upstreams (DoH/DoT), bootstrap servers and filter lists in its UI after signing in |
| `install_adguard` | computed | `dns_filter == adguard` (cannot be set) |
| `hostname_adguard` | `adguard.<domain>` | AdGuard's UI: OIDC sign-in first (permission `dns:filter`); `cname_adguard` (default `adguard`) changes the first label |
| `adguard_upstreams` | `[]` | Prefills a first deploy only, e.g. `[https://dns.google/dns-query, tls://dns.google]`; afterwards upstreams are AdGuard's UI's (fabric keeps only its `[/<zone>/]<ip_bind9>` lines) |
| `adguard_filter_lists` | `[]` | Prefills a first deploy only: `[{name, url}]` |
| `adguard_rules` | `[]` | Your rules, after the generated `@@\|\|<zone>^$important` ones (fabric's names are never blocked); rules added in the UI are kept below them |
| `ip_adguard` / `ip_oauth2proxy` | `10.255.0.31` / `10.255.0.32` | On fabric_net |
| `adguard_mem_limit` | `256m` | Container memory limit |

### 802.1X (optional)
| Variable | Default | Notes |
|---|---|---|
| `install_freeradius` | `false` | FreeRADIUS 3.2: EAP-TLS and MAB decided from the directory (operations.md → 802.1X); needs `install_ldap` |
| `radius_clients` | `[]` | `[{name, address (IP or network), message_authenticator (true)}]`; overlapping addresses refused |
| `radius_people` | `network-staff` (priority 50), `network-guests` (100), no VLANs | Groups whose members may join by password (EAP-TTLS): `[{group, vlan (optional), priority (100; lower wins)}]`. `[]`: no password logins (stays empty) |
| `hostname_radius` | `radius.<domain>` | Name on the EAP-TLS server certificate (`cname_radius` changes the first label) |
| `ip_freeradius` | `10.255.0.98` | On fabric_net (reaches 389-DS) |
| `freeradius_mem_limit` | `128m` | Container memory limit |

Shared secrets are not settings: they live in OpenBao (`radius_secrets`); `fabricctl radius add-client` / `rotate-secret` show them once.

### DHCP (optional)
| Variable | Default | Notes |
|---|---|---|
| `install_kea` | `false` | Kea 3.0 LTS serves DHCP (operations.md → DHCP) |
| `dhcp.interfaces` | — | Host interface(s) to serve, e.g. `[eth0]`; UDP 67 is opened on them only |
| `dhcp.subnets` | — | `[{subnet, pools: ["a - b"], routers, reservations: [{mac, ip, hostname}]}]`; reservations inside the subnet, outside its pools |
| `dhcp.lease_time` | `86400` | Seconds, 300 to 2592000 |
| `dhcp.dns` | `[host_ip]` | DNS servers handed to clients |
| `dhcp.domain` | `domain` | Domain name handed to clients |
| `dhcp.ddns` | `true` | Register client hostnames in DNS |
| `dhcp.ddns_subdomain` | `dhcp` | The dynamic zone is `<ddns_subdomain>.<domain>` |
| `ip_kea_ddns` | `10.255.0.97` | kea-dhcp-ddns on fabric_net (sends the updates to BIND) |
| `kea_mem_limit` | `128m` | Memory limit per Kea container |

The DDNS key's secret is generated (`kea_ddns_secret`, in OpenBao); it is not a setting.
