# Open Fabric — web control

**Open Fabric** (subtitle *web control*) is the browser front end for `fabricctl`. It runs as an unprivileged container (`fabric-web`, systemd service `fabric-web`; the code lives in `webui/`) and is reachable only through nginx at `https://fabric.<domain>` by default — any host name via `webui_hostname`. Every read and change it makes goes through `fabric-agent`, a small privileged host service with a fixed JSON API on a unix socket.

### Table of Contents
- [Features](#features)
- [Architecture](#architecture)
- [Components](#components)
- [Security Model](#security-model)
- [Configuration](#configuration)
- [First-Time Setup](#first-time-setup)
- [Troubleshooting](#troubleshooting)

---

## Features

One tab per service, plus an overview. Tabs marked *optional* are the
services that can be added or removed on a running install (DHCP, 802.1X);
everything else is core. A person sees only the tabs, sub-menus and forms
their permissions allow (see [Who may do what](#who-may-do-what)); the
header has the **Audit log** link and **Sign out**, the footer the fabricctl
version and build.

| Tab | What it does |
|-----|--------------|
| Overview (`/`) | One status light per installed service (`nginx`, `bind9`, `stepca`, `ldap`, `postgres`, `keycloak`, `openbao`, `kea`, `freeradius`, `fluentbit`, `fabric-web`, `fabric-agent`; a service that is not installed is left out). Green: running (and its Docker health check passes, where it has one). Amber: starting. Red: stopped or health check failing, with the reason beside it. Also "N of M services healthy". Needs `status:read` |
| BIND9 · Forward zones (`/bind9?zone=<key>`) | Zone picker; records (A, AAAA, CNAME, MX, TXT, SRV) with each A/AAAA record's automatic PTR (or why it has none); add or delete a record in `vars.yaml`; Apply |
| BIND9 · Reverse zones (`/bind9?view=reverse`) | Read-only: the reverse zones and PTR records generated from the forward A/AAAA records (see [Reverse DNS](operations.md#reverse-dns)), hand-written reverse zones, and addresses that get no PTR, with the reason |
| BIND9 · TSIG keys (`/bind9?view=tsig`) | Keys with their effective update rights and ACLs (never secrets). **New TSIG key for a zone**: a forward zone and one scope — certbot DNS-01 for listed hosts, certbot DNS-01 for any host in the zone, or any name with chosen record types; generated secret or an existing one kept. The secret and the `rfc2136.ini` (download) are shown once. **New secret** (rotate) and **Delete**. Apply publishes. ACLs and update policies: placeholder (`fabricctl acl`) |
| Kea · DHCP (`/kea`) *optional* | Subnets (pools, router, reservation count), reservations with **Remove**, **Reserve** (MAC, address, hostname; saved and applied at once), and live leases from Kea. When DHCP is off: how to turn it on. Needs `dhcp:read`; changes need `dhcp:write`. See [DHCP](operations.md#dhcp-optional-kea) |
| Step-CA · PKI (`/stepca?view=…`) | Sub-menu: **Certificate authority** (root + intermediate subject, expiry, SHA-256; link to `certs.<domain>`), **Sign a CSR** (upload or paste PEM/DER → review names, key, policy → sign), **New key + certificate** (for devices that cannot make a CSR: RSA-2048/3072/4096 or EC P-256/P-384), **Inspect** (decode a certificate, chain or CSR; says whether this fabric issued it), **Convert** (PEM `.crt`, DER `.cer`, full chain `.pem`/`.p7b`, and with its key a `.p12`), **Issued** (every certificate issued by hand, with expiry status). See [Manual certificates](#manual-certificates) |
| 389-DS · Directory (`/dirsrv?view=…`) | **Devices**: list (status light, type, MACs, owner, roles, effective access), add, and a page per device to edit it, see what its roles add up to, manage its linked certificates (issue one from Step-CA, sign its CSR, unlink), delete. **Roles**: what member devices may do (permissions, optional VLAN, priority), add/edit/delete (refused while devices are in it). **People**: the realm's users (locked or active, name, e-mail, groups) and the groups with their members; **Add a person** and **Reset sign-in** (see [People](#who-may-do-what) below); a link to the Keycloak admin console, where admins manage group membership. See [Device access (RBAC)](#device-access-rbac) |
| FreeRADIUS · 802.1X (`/freeradius`) *optional* | The server (host IP, the certificate name supplicants check), RADIUS clients (address, whether Message-Authenticator is required) with **New secret** and **Remove**, **Add client** (a generated secret or one the device already has; shown once), **People**: the directory groups whose members may join by password (EAP-TTLS), with their VLAN and priority, **Map group** and **Remove**, and the recent decisions: accepted or refused, method (EAP-TLS / EAP-TTLS / MAB), device or person, VLAN, MAC, which switch asked, and why. Sub-menu: **Overview** (all of the above), **Connect a switch** (the RADIUS settings filled in for this install, per-port modes, what must stay open, UniFi step by step) and **Connect Windows** (EAP-TLS for fabric's PCs and EAP-TTLS for shared PCs, each with a generated PowerShell script to download: Wired AutoConfig on, the fabric root CA trusted, the server pinned by name and CA, the device certificate imported, the 802.1X profile added; untested on Windows until the hardware test). Needs `radius:read`; changes need `radius:admin`. When 802.1X is off: how to turn it on. See [802.1X](operations.md#8021x-optional-freeradius) |
| OpenBao · Secrets (`/openbao?view=…`) | **Status**: state light (unsealed / sealed / not initialised / unreachable), version, seal, storage, where fabric's secrets live (OpenBao entry version and date), link to `vault.<domain>`, secret engines and sign-in methods (read as `fabric-agent`; no secret values). **Unlock methods**: every key slot (key file, security keys, USB sticks, KMIP HSMs) with presence light, device, key version; kill-switch state; warnings (a key file next to device slots, a single device); add a security key / USB stick / HSM (plugged-in tokens and USB disks are listed from the host), rotate the vault key, test or remove a method — all confirmed by typing the host name, and all need a sign-in from the last 5 minutes (otherwise you are sent to sign in again, then repeat the change). Security keys (PKCS#11 tokens, listed with their PIN state) are tested with SoftHSM2 only and HSMs (KMIP) with the PyKMIP server only; hardware tokens and vendor HSMs are untested. The dev preview runs every flow in memory. **Disk encryption**: a manual guide for LUKS with the same YubiKey (FIDO2) or USB stick (untested with hardware). **Secrets**: state of fabric's own secrets (`fabric/secrets` version and date; never values), a link to OpenBao's own UI (sign in with Keycloak) for `apps/`, and the break-glass commands |
| Apply (button on the BIND9 tab and after a TSIG change) | fabric-agent runs the same apply as `sudo fabricctl --apply` (`interactive.py --apply`) — the whole deployment, not only DNS; the output is shown. Needs `dns:write` |
| Audit log (`/audit`, header link) | The last 200 lines of `/opt/fabric/archive/audit.log`, newest first: logins, denials, and every change from the web UI and the CLI. Needs `audit:read` |

DNS record and TSIG edits only change `vars.yaml`; nothing is published until **Apply**. DHCP reservations and 802.1X changes are saved and applied at once. Every edit of `vars.yaml` and every apply takes the vars lock (`/opt/fabric/config/.vars.lock`, shared with the CLI), so concurrent sessions do not interleave.

### Manual certificates

For the devices that cannot use ACME: switches, printers, appliances, VPN
boxes, Windows machines with `certreq`.

- **Signing policy.** The CSR's signature must verify. Its key must be RSA ≥ 2048,
  EC P-256/384/521 or Ed25519. Its names must be DNS names, IP addresses or
  e-mail addresses (URIs and other names are refused). Validity runs from 1 day
  to [`pki_manual_max_days`](vars.md#pki_manual_max_days) (default 5 years).
  Whatever the CSR asks for, the result is a **leaf** (serverAuth + clientAuth)
  from fabric's template: a request for `CA:TRUE` is shown in the review and
  ignored. If the CSR has no SANs, the CN becomes one.
- **Generated keys are not kept.** A generated private key exists only in the
  response. It is shown once as PEM and as a `.p12` with a generated
  password. Downloads are `data:` links on the result page, so there is never
  a URL to fetch the key again. Nothing is written to disk except a 0600
  temp dir that is removed at once.
- **Inspect refuses private keys** unread. **Convert** uses a supplied key
  only to build the `.p12`, after checking it matches the certificate.
- **Ledger.** Every hand-issued certificate is recorded in
  `/opt/fabric/archive/issued-certs.jsonl` (0600): subject, names, serial,
  expiry, fingerprint, who issued it and how. The ledger holds no keys. Each
  issue is also written to the audit log (`PKI_SIGN_CSR`, `PKI_ISSUE`,
  `PKI_CONVERT`).
- Signing uses the Step-CA intermediate key through the pinned step image
  (`docker run --network none`), as setup does. The CA key never enters the
  web UI container.

### Device access (RBAC)

People are managed in **Keycloak** (which writes them to 389-DS). **389-DS**
holds the *devices* and what they may do. Device permissions are a separate
set from the people's fabric permissions in [Who may do what](#who-may-do-what):
they say what a device may do on the network, not what a person may do in
this web UI.

- **Device** (`cn=<name>,ou=devices,ou=<site_name>,<base>` — this
  site's part of the directory): type, MAC addresses (each MAC belongs to one device only), owner
  (a user), description, enabled flag, the roles it is in (`fabricRoleName`)
  and the SHA-256 fingerprints of certificates issued to it.
- **Role** (`cn=<name>,ou=device-roles,<base>`, organisation-wide):
  permissions, an optional VLAN and a priority. Its members are the devices
  that name it.
- **Default roles** (created once by setup, then yours to edit or delete):
  `workstations`, `phones-tablets`, `servers` (`network:eap-tls`,
  workstations and servers also `pki:acme`), `printers`, `iot`
  (`network:mab`) and `network-gear` (`pki:scep`); no VLANs.
- **Effective access** is the union of a device's roles' permissions. The
  VLAN comes from the role with the lowest priority number. A disabled
  device gets nothing.

| Device permission | Grants | Enforced by (once installed) |
|---|---|---|
| `network:eap-tls` | Join the network with its certificate (802.1X EAP-TLS) | FreeRADIUS |
| `network:mab` | Join the network by MAC address (printers, IoT) | FreeRADIUS |
| `dns:dhcp-register` | Register its DHCP hostname in the DHCP zone | Kea DHCP-DDNS |
| `pki:acme` | Obtain and renew certificates by ACME | Step-CA |
| `pki:scep` | Enrol certificates by SCEP (MDM, network gear) | Step-CA |

FreeRADIUS enforces `network:eap-tls` and `network:mab` (and the VLAN)
when 802.1X is on; `dns:dhcp-register`, `pki:acme` and `pki:scep` are not
enforced yet. The schema (`dirsrv/seed/05-schema.ldif`) is fabric's own:
`fabricDevice`, `fabricRole`, OID arc
`2.25.204492767351757179914238406906488345409`.

The web UI changes the directory through fabric-agent bound as
**`cn=device_admin`**, which the ACIs allow to change only `ou=devices`
and `ou=device-roles`. It can read people but not change them, not change
groups, and never read passwords. Every change is audited
(`DEVICE_*`, `ROLE_*`).

---

## Architecture

```
browser ──mTLS──> nginx ──unix──> webui container ──unix──> fabric-agent (host, root)
                  (container)     /opt/webui/run/web.sock   /opt/webui/agent/agent.sock
                                  uid 912, no caps, ro FS   fixed API, audited
```

The web app (TLS header checks, OIDC, sessions, HTML) holds no privilege: no Docker socket, no host config, no capabilities, read-only root FS. It joins `fabric_net` only to reach Keycloak and publishes no ports. The privileged half (`fabric-agent`) does the work — edits `vars.yaml` and runs the apply, reads service status, signs certificates through the Step-CA image, changes devices and roles in 389-DS, creates and resets people through the Keycloak admin API, manages OpenBao's unlock methods, and writes the audit log — only through its [fixed API](#fixed-api), never as a general executor. Every call carries the signed-in person's ID token, which the agent verifies itself.

---

## Components

| Item | Location |
|------|----------|
| Container | `fabric-web` — `/opt/webui/docker-compose.yml` from `fabricctl/jinja/webui/docker-compose.yml.j2`; image `image_webui` (`fabric/web:local`) built locally from `webui/Dockerfile` (the validated, digest-pinned Debian base `image_debian` + `python3`, `python3-jinja2`, `openssl`, `ca-certificates`, `tini`); memory limit 96 MB on 3-4 GB hosts; logs to the host journal (`journalctl -u fabric-web`, or `docker logs fabric-web`) |
| Container code | `webui/` (`server.py` and `handler.py`, the gates in `security/` and `session/`, `routes/`, the pages in `views/` with `templates/` and `static/`, the agent client in `agentclient/`, `oidc.py`, `tlsclient.py`; stdlib + `jinja2`), copied to `/opt/webui/build/app/` at deploy time and baked into the image |
| Container user | `service_users.webui` (default uid/gid `912`) + `group_add` nginx gid; `read_only`, `cap_drop: ALL`, `no-new-privileges`, tmpfs `/tmp`; `ip_webui` (default `10.255.0.80`) on `fabric_net` |
| Container mounts | `/opt/webui/config` → `/config` (ro); `/opt/stepca/data/certs` → `/certs` (ro, public CA certs only); `/opt/webui/run` → `/run/webui`; `/opt/webui/agent` → `/agent` (ro) |
| Config | `/opt/webui/config/webui.json` (webui uid, `0400`; contains the OIDC client secret; in-container paths incl. `agent_socket`) — from `fabricctl/jinja/webui/webui.json.j2` |
| fabric-web unit | `/etc/systemd/system/fabric-web.service` — standard compose wrapper; requires `fabric-agent` (upgrades retire the old `webui` unit and container) |
| Web socket | `/opt/webui/run/web.sock` (socket `0660`, group nginx; dir `webui:nginx 0750`), created by the container, mounted into nginx at `/srv/webui` |
| fabric-agent | `/opt/fabric/lib/agent/server.py` (routes to `fabricctl/lib/fabriclib/`); unit `/etc/systemd/system/fabric-agent.service` from `fabricctl/jinja/systemd/fabric-agent.service.j2` (root, sandboxed, no network listener) |
| Agent socket | `/opt/webui/agent/agent.sock` (`root:<webui gid> 0660`; dir `root:<webui gid> 0750`) |
| nginx vhost | `server_name hostname_mgr`; `ssl_verify_client on`, `ssl_verify_depth 2`, trust `/opt/nginx/certs/client-ca/ca-bundle.pem` (intermediate + root) |
| Server cert | `fabric.<domain>` offline Step-CA leaf, issued by the `certs` setup step (renew: `fabricctl certs`) |
| Keycloak | realm `webui_realm`; client `fabric-webui`; a realm role per fabric permission (`fabric:<area>:<action>`) and a composite role per bundle (the admin bundle is `webui_admin_role`, default `fabric-admin`); flow `fabric-webui-mfa` (TOTP) — created by `keycloak_bootstrap.py`, see [keycloak.md](keycloak.md) |

---

## Security Model

Every request must pass all gates:

| # | Gate | Enforced by |
|---|------|-------------|
| 1 | TLS client certificate that chains to the core root CA within depth 2 | nginx (`ssl_verify_client on`) — no cert → `400` |
| 2 | Certificate issued **directly** by the Step-CA intermediate (leaves under a subordinate CA are rejected) | webui (issuer DN check) → `403` |
| 3 | Keycloak login: OIDC authorization code + PKCE (S256), always with `prompt=login` (password and TOTP every time, even with a Keycloak session open); the login attempt is bound to the certificate and expires after 10 min; ID token signature (RS256), issuer, audience, azp, expiry and nonce verified | webui + Keycloak |
| 4 | TOTP second factor (flow `fabric-webui-mfa`, bound to the `fabric-webui` and `fabric-openbao` clients only) | Keycloak |
| 5 | Keycloak username **equals** the client certificate CN | webui → `403` |
| 6 | User holds at least one fabric permission (a bundle, see [Who may do what](#who-may-do-what)) | webui → `403` |
| 6b | Every fabric-agent call carries the user's ID token; the agent verifies it itself and needs the route's permission | fabric-agent → `401` / `403` |
| 7 | Session bound to the certificate fingerprint and CN; idle timeout 15 min, max 8 h (`webui_session_idle`, `webui_session_max`); the ID token is renewed with Keycloak a minute before it expires, so a disabled user or removed role ends the session within minutes. Sessions live only in memory: restarting `fabric-web` signs everyone out | webui (session dropped → re-login) |
| 8 | State-changing requests are POST-only with a per-session CSRF token and an `Origin` header equal to the web UI's own address | webui → `403` |
| 9 | Changes to OpenBao's unlock methods need a sign-in from the last 5 minutes | webui (→ sign in again) |

nginx always overwrites the `X-SSL-Client-*` headers, and webui listens only on a unix socket that only nginx can reach, so the certificate headers cannot be forged. Responses carry a strict CSP (no scripts at all; styles and images from the web UI only; forms may post only to the web UI and Keycloak), `Cache-Control: no-store`, `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`, `Referrer-Policy: no-referrer` and `Cross-Origin-Opener-Policy: same-origin`; nginx adds HSTS. Cookies are `__Host-` cookies (Secure, HttpOnly): the session cookie is `SameSite=Strict`, the short-lived login cookie `SameSite=Lax` (it must come back with Keycloak's redirect).

### Who may do what

Permissions are Keycloak realm roles named `fabric:<area>:<action>` (below
without the `fabric:` prefix); **bundles** are composite roles holding a set of
permissions, granted to directory groups (created by setup, add people to
them). The list lives in `fabriclib/rbac/permissions.py` (`PERMISSIONS`,
`BUNDLES`); `fabricctl --keycloak-sync` converges Keycloak to it.

| Permission | Grants | Needed by |
|---|---|---|
| `status:read` | See the services' health | Overview tab |
| `dns:read` | See zones, records, reverse zones and TSIG keys (names and rights, never secrets) | BIND9 tab |
| `dns:write` | Add and delete DNS records, and **Apply** — which runs the whole deployment, not only DNS | BIND9 tab |
| `tsig:manage` | Create TSIG keys, give them a new secret, delete them | BIND9 → TSIG keys |
| `dns:filter` | Open AdGuard Home's own UI (lists, upstreams, rules, clients) with the optional DNS filter | `https://adguard.<domain>` (oauth2-proxy checks it) |
| `dhcp:read` | See DHCP subnets, reservations and leases | Kea tab |
| `dhcp:write` | Add and remove DHCP subnets, reservations, options and client classes (applied at once) | Kea tab |
| `pki:read` | See the CA and the certificates issued by hand; inspect a certificate or CSR; review a CSR before signing | Step-CA tab |
| `pki:issue` | Generate a key + certificate; convert a certificate (with its key to `.p12`) | Step-CA → New key + certificate, Convert |
| `pki:sign` | Sign an uploaded CSR | Step-CA → Sign a CSR |
| `pki:link-device` | Link a certificate to a device, or unlink it (signing or issuing *for* a device links it with `pki:sign` / `pki:issue` alone) | 389-DS → a device's Certificates |
| `devices:read` | See devices and device roles | 389-DS → Devices, Roles |
| `devices:enroll` | Add devices | 389-DS → Add a device |
| `devices:admin` | Change, disable and delete devices | 389-DS → a device's page |
| `roles:admin` | Create, change and delete device roles | 389-DS → Roles |
| `radius:read` | See 802.1X: server, RADIUS clients, mapped groups, recent decisions, setup guides | FreeRADIUS tab |
| `radius:admin` | Add, re-key and remove RADIUS clients; map and unmap groups (applied at once) | FreeRADIUS tab |
| `people:read` | See the realm's users and groups | 389-DS → People |
| `people:create` | Add a person (a realm user with a one-time password) | 389-DS → People |
| `people:reset` | Reset a person's sign-in: new one-time password, TOTP removed, sessions ended | 389-DS → People |
| `vault:status` | See OpenBao's state, secret engines and unlock methods, and the host's tokens and USB disks | OpenBao tab |
| `vault:unlock` | Add, test and remove unlock methods; rotate the vault key | OpenBao → Unlock methods |
| `audit:read` | Read the audit log | Audit log |
| `system:admin` | Meant for services, updates and settings; no web UI action needs it yet. Today it only lets its holder reset the sign-in of people in fabric groups (see *People* below) | — |

| Group | Bundle | Permissions | In short |
|---|---|---|---|
| `admins` (`webui_admin_group`) | `fabric-admin` (`webui_admin_role`) | every permission above | everything |
| `auditors` | `fabric-auditor` | `status:read`, `dns:read`, `dhcp:read`, `pki:read`, `devices:read`, `radius:read`, `people:read`, `vault:status`, `audit:read` | read every tab and the audit log; change nothing |
| `network-operators` | `fabric-network-operator` | `status:read`, `dns:read`, `dns:write`, `tsig:manage`, `dns:filter`, `dhcp:read`, `dhcp:write`, `pki:read`, `vault:status` | DNS records and Apply, TSIG keys, the DNS filter's UI, DHCP reservations; read PKI and vault status; **no** device management |
| `equipment-operators` | `fabric-equipment-operator` | `status:read`, `dns:read`, `pki:read`, `pki:link-device`, `devices:read`, `devices:enroll`, `devices:admin`, `roles:admin`, `radius:read`, `radius:admin` | devices, device roles, 802.1X, link certificates to devices |
| `pki-operators` | `fabric-pki-operator` | `status:read`, `pki:read`, `pki:issue`, `pki:sign`, `pki:link-device`, `devices:read` | sign CSRs, issue key pairs, convert, link certificates to devices |
| `helpdesk` | `fabric-helpdesk` | `status:read`, `dns:read`, `pki:read`, `devices:read`, `devices:enroll`, `people:read`, `people:create`, `people:reset` | add a person, reset a sign-in, enrol devices; read DNS, PKI and devices |

Own bundles: create a composite role in Keycloak holding `fabric:*` roles and
grant it to a group. The pages hide what a person cannot use; **fabric-agent
enforces it** on every call, from the token's roles
(`fabriclib/rbac/required_permission.py`; routes not listed there are
refused), and writes the token's user to the audit log. A request crafted
past the pages gets `403 Not allowed: you need the permission …`. The dev
preview shows the pages as a bundle sees them: `devserver.py --as fabric-auditor`.

**People (Directory → People).** *Add a person* creates the account in
Keycloak (written to 389-DS), in the plain `users` group only, with a
one-time password shown once; at the first sign-in they choose their own
and set up TOTP. *Reset sign-in* gives a new one-time password, removes
their TOTP (enrolled again) and ends their sessions. Someone in a fabric
group (`webui_admin_group` or any group that carries a bundle: admins,
auditors, operators, helpdesk) can only be reset by an admin (`system:admin`):
otherwise the helpdesk could take over an admin's single sign-on
(OpenBao's UI needs no client certificate). Group membership — which
bundle a person holds — is managed by admins in Keycloak.

**OpenBao's own UI** follows the bundles too: `fabric-admin` gets the
`fabric-admin` policy (application secrets, configuration read-only),
`fabric-auditor` the `fabric-auditor` policy (which application secrets
exist and their history, never a value). Other bundles cannot sign in there
unless an admin maps them (`OIDC_BUNDLE_POLICIES` in
`fabriclib/vault/constants.py`).

### Privilege separation

A compromise of the web app yields only the webui container: uid 912, no capabilities, read-only FS, no Docker socket, no host config (only its own `webui.json` and the public CA certs are mounted). The only path to the host is `fabric-agent`:

| Control | Detail |
|---------|--------|
| Socket access | `agent.sock` is `0660 root:<webui gid>` in a `0750` dir; other host users cannot reach it |
| Peer check | `SO_PEERCRED` on every connection: only the webui uid and root are accepted (right group, wrong uid → `403 peer not allowed`) |
| Sign-in token | Every call from the web UI carries the person's Keycloak ID token (`Authorization: Bearer`); the agent verifies it itself (RS256 against the realm's keys, issuer, audience, expiry) and allows the call only if the token grants the route's permission. The acting user in the audit log is the token's user, never a value from the request. Root peers (the host itself) need no token |
| Fixed API | The routes in [Fixed API](#fixed-api) below, each with the permission it needs (`fabriclib/rbac/required_permission.py`). Anything else is refused (`403 not allowed`) |
| Validation | Every input is validated in the fabriclib function the route calls (e.g. records in `fabriclib/dns/validate_record.py`); text fields must be text, lists at most 100 items; body ≤ 64 KiB; a root peer's `actor` must match `^[A-Za-z0-9][A-Za-z0-9._@-]{0,63}$` |
| Audit | Every change is written to `/opt/fabric/archive/audit.log` with the acting user |
| Sandbox | systemd hardening (`NoNewPrivileges`, `ProtectHome`, `ProtectKernel*`, `RestrictNamespaces`, ...); no network listener; IP access limited to localhost + `fabric_subnet` |

### Fixed API

`fabric-agent` answers only these routes (JSON over its unix socket). "any
sign-in" means any signed-in fabric user.

| Method | Route | Needs |
|---|---|---|
| GET | `/v1/version` | any sign-in |
| GET | `/v1/services` | `status:read` |
| GET | `/v1/zones`, `/v1/zones/<key>`, `/v1/reverse-zones`, `/v1/tsig` | `dns:read` |
| GET | `/v1/audit` | `audit:read` |
| GET | `/v1/dhcp` | `dhcp:read` |
| GET | `/v1/radius`, `/v1/radius/guides` | `radius:read` |
| GET | `/v1/pki/{ca,issued}` | `pki:read` |
| GET | `/v1/devices` | `devices:read` |
| GET | `/v1/people` | `people:read` |
| GET | `/v1/vault`, `/v1/vault/{slots,devices}` | `vault:status` |
| POST | `/v1/events` (`LOGIN`, `LOGOUT`, `LOGIN_DENIED` only) | any sign-in |
| POST | `/v1/zones/<key>/records`, `/v1/zones/<key>/records/delete`, `/v1/apply` | `dns:write` |
| POST | `/v1/pki/{describe-csr,inspect}` | `pki:read` |
| POST | `/v1/pki/sign` | `pki:sign` |
| POST | `/v1/pki/{issue,convert}` | `pki:issue` |
| POST | `/v1/tsig`, `/v1/tsig/<name>/{rotate,delete}` | `tsig:manage` |
| POST | `/v1/vault/rotate`, `/v1/vault/slots/{add-usb,add-security-key,add-hsm}`, `/v1/vault/slots/<id>/{test,remove}` | `vault:unlock` |
| POST | `/v1/devices` | `devices:enroll` |
| POST | `/v1/devices/<name>`, `/v1/devices/<name>/delete` | `devices:admin` |
| POST | `/v1/devices/<name>/certs` | `pki:link-device` |
| POST | `/v1/roles`, `/v1/roles/<name>`, `/v1/roles/<name>/delete` | `roles:admin` |
| POST | `/v1/people` | `people:create` |
| POST | `/v1/people/<uid>/reset` | `people:reset` (members of fabric groups: also `system:admin`) |
| POST | `/v1/dhcp/reservations`, `/v1/dhcp/reservations/<mac>/delete`, `/v1/dhcp/subnets`, `/v1/dhcp/subnets/{update,delete}`, `/v1/dhcp/options`, `/v1/dhcp/options/delete`, `/v1/dhcp/classes`, `/v1/dhcp/classes/<name>/delete` | `dhcp:write` |
| POST | `/v1/radius/clients`, `/v1/radius/clients/<name>/{rotate,delete}`, `/v1/radius/people`, `/v1/radius/people/<group>/delete` | `radius:admin` |

---

## Configuration

Enabled by default whenever `install_keycloak: true` (`install_webui` is forced off without Keycloak).

| Variable | Default | Notes |
|----------|---------|-------|
| `install_webui` | `true` | Effective only with Keycloak |
| `webui_hostname` | `fabric.<domain>` | The web UI's address — any host name. Inside the domain a CNAME to this host is added automatically; outside it, point DNS at the host yourself. The certificate and the OIDC redirect follow |
| `cname_mgr` | `fabric` | The default name's label (`<cname_mgr>.<domain>`) when `webui_hostname` is not set |
| `webui_realm` | `domain` | Keycloak realm |
| `webui_admin_role` | `fabric-admin` | The admin bundle (every permission), granted to `webui_admin_group` |
| `webui_admin_group` | `admins` | Group granted the role; its members can only be reset by an admin |
| `webui_admin_user` | account that ran `sudo`, else `fabricadmin` | First admin, created by setup (asked for interactively; kept once chosen) |
| `webui_admin_email` | `<user>@<domain>` | Mail attribute of that user (Keycloak's profile needs one) |
| `webui_client_cert_days` | `365` | Lifetime of the admins' client certificates |
| `webui_session_idle` | `900` | Seconds |
| `webui_session_max` | `28800` | Seconds |
| `webui_oidc_secret` | *(generated)* | With fabric's secrets (OpenBao) |

Related: `image_webui` (`fabric/web:local`), `ip_webui` (`10.255.0.80`), `service_users.webui` (uid/gid `912`) — see [vars.md](vars.md).

After changing the realm/role/group vars: `sudo fabricctl --apply` then `sudo fabricctl --keycloak-sync`.

The groups that carry the other bundles (`auditors`, `network-operators`, `equipment-operators`, `pki-operators`, `helpdesk`) come from `ldap_groups` (each entry's `bundle`); see [vars.md](vars.md).

Image updates: `sudo fabricctl images update fabric-web` rebuilds the image on the validated Debian base (pinned by digest). The Debian base is shared (`image_debian`), so bind9, dirsrv, kea and freeradius move to it together. An apply that changes the app code or Dockerfile rebuilds the image; `fabric-web` is always restarted last with `--no-block`, since the apply may have been started from the web UI.

---

## First-Time Setup

`fabricctl setup` does the server side for you (the `admin` step):

- creates the first admin `webui_admin_user` in 389-DS (default: the account that ran `sudo`, else `fabricadmin`) and adds it to `admins`, which Keycloak maps to `fabric-admin`;
- gives it a generated initial password that Keycloak makes you change at the first login;
- issues its client certificate (CN = the username) as a password-protected `.p12`;
- puts all of it, with the fabric root CA and a README, in **`~/fabric-admin/`** of the account that ran setup (secrets `0600`).

Re-running setup keeps the user and its password, and renews the certificate only when it is due. `fabricctl doctor` checks the whole chain: Keycloak grants the admin `fabric-admin` and the certificate chains to the CA with CN = username.

What is left is your computer, which setup cannot touch:

1. **Copy the kit** to your computer, e.g. `scp -r <you>@<fabric-host>:fabric-admin .`
2. **Trust the root CA**: `root-ca.cer` (Windows) or `root-ca.crt` (macOS, Linux) from the kit; every system, format and installer is on `https://certs.<domain>/`.
3. **Import `<user>.p12`** into your browser (password in `p12-password.txt`).
4. **Resolve `fabric.<domain>`**: use fabric as your DNS server (or add a hosts entry).
5. **Browse** to `https://fabric.<domain>`, pick the certificate, log in with the password from `initial-password.txt`, choose a new password and **enrol TOTP** (scan the QR code with an authenticator app). Every later sign-in asks for the password and the one-time code.

Then delete `initial-password.txt` and `p12-password.txt`.

**More admins or operators:** the person needs an account (389-DS → People → *Add a person*, or the Keycloak admin console) in the group of their bundle (`admins`, `auditors`, …: LDAP, or the Keycloak admin console: *Users → Groups → Join group*), then

```bash
sudo fabricctl client-cert <keycloak-username>
```

which writes `~/fabric-admin/<username>.p12` and shows its password once. `fabricctl --client-cert <user>` is the same command.

Use **Sign out** to end both the web UI session and the Keycloak session.

---

## Dev preview

To look at the pages without a CA, client certificate, Keycloak or a running install:

```bash
python3 webui/devserver.py            # from a checkout (needs python3-jinja2) -> http://127.0.0.1:8080
docker run --rm -p 127.0.0.1:8080:8080 --entrypoint /usr/bin/python3 \
    fabric/web:local /app/webui/devserver.py --bind 0.0.0.0     # from the image, on a fabric host
```

It renders the real pages (`webui/views`) with sample data (`webui/devpreview/`) under an orange **DEV PREVIEW** banner. `--as <bundle>` (e.g. `--as fabric-auditor`) shows the pages as that bundle sees them; the default is every permission. Changes work in memory only — there is no fabric-agent, nothing is saved, rendered or reloaded, and a restart resets everything. `/preview/denied` shows a refused sign-in. It is a separate entry point on purpose: the production server (`server.py`) has no dev switch, so a real install can never run without sign-in. It listens on 127.0.0.1 unless told otherwise; never expose it.

## Troubleshooting

| Symptom | Cause / Fix |
|---------|-------------|
| `400 No required SSL certificate was sent` | No client cert presented. Import the `.p12`; restart the browser if it cached "no certificate" for the site. |
| `400 The SSL certificate error` | Cert not from this fabric's CA (or expired). Mint a new one with `fabricctl client-cert <user>`. |
| `403` "client certificate issued by this fabric's certificate authority is required" | Cert chains to the root but was not issued directly by the Step-CA intermediate (e.g. under a sub-CA). |
| `403` "certificate does not belong to this user" | Keycloak username ≠ cert CN. Mint a cert for the exact username. |
| `403` "has no fabric role" | User in none of the fabric groups (`admins`, `auditors`, …). Fix membership and sign in again; if the group's bundle is not granted in Keycloak, `sudo fabricctl --keycloak-sync`. |
| `403` "Not allowed: you need the permission …" | The user's bundle does not include that action: add them to a group whose bundle does. |
| `403` "Not allowed: not allowed" | The page asked fabric-agent for a route it does not know (a web UI and agent from different versions): re-run `sudo fabricctl --apply`. |
| `403` "CSRF check failed" | Stale page or cross-origin post. Reload and retry. |
| Login loops / "Login expired" | Login took over 10 min or started in another browser. Start again at `/`. |
| Everyone signed out at once | `fabric-web` restarted (sessions live in memory), e.g. after an apply that rebuilt it. Sign in again. |
| `502 Bad Gateway` | `fabric-web` container not running or socket missing: `systemctl status fabric-web`, `docker ps -a --filter name=fabric-web`, `ls -l /opt/webui/run/`. |
| `503` "fabric-agent service is unavailable" | Agent down or socket missing: `systemctl status fabric-agent`, `journalctl -u fabric-agent -e`, `ls -l /opt/webui/agent/`. |
| `500` / any error | `journalctl -u fabric-web -e` or `docker logs fabric-web` (container), `journalctl -u fabric-agent -e` (agent) |
| Keycloak client/flow missing or wrong | `sudo fabricctl --keycloak-sync` (idempotent) |

Denied logins are recorded as `LOGIN_DENIED` in `/opt/fabric/archive/audit.log`.
