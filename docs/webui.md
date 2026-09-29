# webui Management UI

webui is a browser front end for `fabricctl`. It runs as an unprivileged container (`webui`, systemd service `webui`) and is reachable only through nginx at `https://fabric.<domain>` by default — any host name via `webui_hostname`. Every read and change it makes goes through `fabric-agent`, a small privileged host service with a fixed JSON API on a unix socket.

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
everything else is core.

| Tab | What it does |
|-----|--------------|
| Overview (`/`) | One status light per service (`nginx`, `bind9`, `stepca`, `ldap`, `postgres`, `keycloak`, `openbao`, `kea`, `freeradius`, `webui`, `fabric-agent`). Green: running (and its Docker health check passes). Amber: starting. Red: stopped or health check failing, with the reason beside it. Also "N of M services healthy" and the version/build |
| BIND9 · Forward zones (`/bind9?zone=<key>`) | Zone picker; records (A, AAAA, CNAME, MX, TXT, SRV) with each A/AAAA record's automatic PTR (or why it has none); add or delete a record in `vars.yaml`; Apply |
| BIND9 · Reverse zones (`/bind9?view=reverse`) | Read-only: the reverse zones and PTR records generated from the forward A/AAAA records (see [Reverse DNS](operations.md#reverse-dns)), hand-written reverse zones, and addresses that get no PTR, with the reason |
| BIND9 · TSIG keys (`/bind9?view=tsig`) | Keys with their effective update rights and ACLs (never secrets). **New TSIG key for a zone**: a forward zone and one scope — certbot DNS-01 for listed hosts, certbot DNS-01 for any host in the zone, or any name with chosen record types; generated secret or an existing one kept. The secret and the `rfc2136.ini` (download) are shown once. **New secret** (rotate) and **Delete**. Apply publishes. ACLs and update policies: placeholder (`fabricctl acl`) |
| Kea · DHCP (`/kea`) *optional* | Placeholder — left intentionally blank |
| Step-CA · PKI (`/stepca?view=…`) | Sub-menu: **Certificate authority** (root + intermediate subject, expiry, SHA-256; link to `certs.<domain>`), **Sign a CSR** (upload or paste PEM/DER → review names, key, policy → sign), **New key + certificate** (for devices that cannot make a CSR: RSA-2048/3072/4096 or EC P-256/P-384), **Inspect** (decode a certificate, chain or CSR; says whether this fabric issued it), **Convert** (PEM `.crt`, DER `.cer`, full chain `.pem`/`.p7b`, and with its key a `.p12`), **Issued** (every certificate issued by hand, with expiry status). See [Manual certificates](#manual-certificates) |
| 389-DS · Directory (`/dirsrv?view=…`) | **Devices**: list (status light, type, MACs, owner, roles, effective access), add, and a page per device to edit it, see what its roles add up to, manage its linked certificates (issue one from Step-CA, sign its CSR, unlink), delete. **Roles**: what member devices may do (permissions, optional VLAN, priority), add/edit/delete (refused while devices are in it). **People**: users and groups, read-only, with a link to the Keycloak admin console — people are managed in Keycloak. See [Device access (RBAC)](#device-access-rbac) |
| FreeRADIUS · 802.1X (`/freeradius`) *optional* | Placeholder — left intentionally blank |
| OpenBao · Secrets (`/openbao?view=…`) | **Status**: state light (unsealed / sealed / not initialised / unreachable), version, seal, storage, where fabric's secrets live (OpenBao entry version and date), link to `vault.<domain>`, secret engines and sign-in methods (read as `fabric-agent`; no secret values). **Unlock methods**: every key slot (key file, security keys, USB sticks, KMIP HSMs) with presence light, device, key version; kill-switch state; warnings (a key file next to device slots, a single device); add a security key / USB stick / HSM (plugged-in tokens and USB disks are listed from the host), rotate the vault key, remove a method — all confirmed by typing the host name. Testing, removing, rotating and adding USB sticks and security keys (PKCS#11 tokens, listed from the host with their PIN state; untested on hardware tokens) are live and need a sign-in from the last 5 minutes; adding an HSM shows as "arrives next". The dev preview runs every flow in memory. **Secrets**: placeholder |
| Apply | fabric-agent runs the same apply as `sudo fabricctl --apply` (`interactive.py --apply`); the output is shown |
| Audit (`/audit`) | Last 200 lines of `/opt/fabric/archive/audit.log` (logins, denials, record edits, applies) |

Record edits only change `vars.yaml`; nothing is published until **Apply**. Edits and applies take a lock file (`/opt/fabric/config/.webui.lock`) so concurrent web sessions do not interleave.

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

People sign up and are managed in **Keycloak**. **389-DS** holds the
*devices* and what they may do:

- **Device** (`cn=<name>,ou=devices,<base>`): type, MAC addresses (each MAC
  belongs to one device only), owner (a user), description, enabled flag,
  and the SHA-256 fingerprints of certificates issued to it.
- **Role** (`cn=<name>,ou=device-roles,<base>`, a group of devices):
  permissions, an optional VLAN and a priority.
- **Effective access** is the union of a device's roles' permissions. The
  VLAN comes from the role with the lowest priority number. A disabled
  device gets nothing.

| Permission | Grants | Enforced by (once installed) |
|---|---|---|
| `network:eap-tls` | Join the network with its certificate (802.1X EAP-TLS) | FreeRADIUS |
| `network:mab` | Join the network by MAC address (printers, IoT) | FreeRADIUS |
| `dns:dhcp-register` | Register its DHCP hostname in the DHCP zone | Kea DHCP-DDNS |
| `pki:acme` | Obtain and renew certificates by ACME | Step-CA |
| `pki:scep` | Enrol certificates by SCEP (MDM, network gear) | Step-CA |

Nothing enforces these yet: FreeRADIUS, Kea and SCEP read them when they
are added. The schema (`dirsrv/seed/05-schema.ldif`) is fabric's own:
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

The web app (TLS header checks, OIDC, sessions, HTML) holds no privilege: no Docker socket, no host config, no capabilities, read-only root FS. It joins `fabric_net` only to reach Keycloak and publishes no ports. The privileged half (`fabric-agent`) edits `vars.yaml`, runs the apply, reads `systemctl` status and writes the audit log — only through its fixed API, never as a general executor.

---

## Components

| Item | Location |
|------|----------|
| Container | `webui` — `/opt/webui/docker-compose.yml` from `fabric/jinja/webui/docker-compose.yml.j2`; image `image_webui` (`fabric/webui:local`) built locally from `fabric/jinja/webui/build/Dockerfile` (`debian:trixie-slim` + `python3`, `python3-jinja2`, `openssl`, `tini`) |
| Container code | `fabric/lib/webui/` (`server.py`, `oidc.py`, `tlsclient.py`, `agentclient.py`, `views.py`; stdlib + `jinja2`), copied to `/opt/webui/build/app/` at deploy time and baked into the image |
| Container user | `service_users.webui` (default uid/gid `912`) + `group_add` nginx gid; `read_only`, `cap_drop: ALL`, `no-new-privileges`, tmpfs `/tmp`; `ip_webui` (default `10.255.0.80`) on `fabric_net` |
| Container mounts | `/opt/webui/config` → `/config` (ro); `/opt/stepca/data/certs` → `/certs` (ro, public CA certs only); `/opt/webui/run` → `/run/webui`; `/opt/webui/agent` → `/agent` (ro) |
| Config | `/opt/webui/config/webui.json` (webui uid, `0400`; contains the OIDC client secret; in-container paths incl. `agent_socket`) — from `fabric/jinja/webui/webui.json.j2` |
| webui unit | `/etc/systemd/system/webui.service` — standard compose wrapper; requires `fabric-agent` |
| Web socket | `/opt/webui/run/web.sock` (socket `0660`, group nginx; dir `webui:nginx 0750`), created by the container, mounted into nginx at `/srv/webui` |
| fabric-agent | `/opt/fabric/lib/agent/server.py` (routes to `fabric/lib/fabriclib/`); unit `/etc/systemd/system/fabric-agent.service` from `fabric/jinja/systemd/fabric-agent.service.j2` (root, sandboxed, no network listener) |
| Agent socket | `/opt/webui/agent/agent.sock` (`root:<webui gid> 0660`; dir `root:<webui gid> 0750`) |
| nginx vhost | `server_name hostname_mgr`; `ssl_verify_client on`, `ssl_verify_depth 2`, trust `/opt/nginx/certs/client-ca/ca-bundle.pem` (intermediate + root) |
| Server cert | `fabric.<domain>` offline Step-CA leaf, issued by the `certs` setup step (renew: `fabricctl certs`) |
| Keycloak | realm `webui_realm`, client `fabric-webui`, role `fabric-admin`, flow `fabric-webui-mfa` — created by `keycloak_bootstrap.py` |

---

## Security Model

Every request must pass all gates:

| # | Gate | Enforced by |
|---|------|-------------|
| 1 | TLS client certificate that chains to the core root CA within depth 2 | nginx (`ssl_verify_client on`) — no cert → `400` |
| 2 | Certificate issued **directly** by the Step-CA intermediate (leaves under a subordinate CA are rejected) | webui (issuer DN check) → `403` |
| 3 | Keycloak login: OIDC authorization code + PKCE (S256); ID token signature, issuer, audience, azp, expiry and nonce verified | webui + Keycloak |
| 4 | TOTP second factor (flow `fabric-webui-mfa`, bound to the `fabric-webui` client only) | Keycloak |
| 5 | Keycloak username **equals** the client certificate CN | webui → `403` |
| 6 | User holds realm role `webui_admin_role` (default `fabric-admin`, granted to LDAP group `webui_admin_group`, default `admins`) | webui → `403` |
| 7 | Session bound to the certificate fingerprint; idle timeout 15 min, max 8 h | webui (session dropped → re-login) |
| 8 | State-changing requests are POST-only with a per-session CSRF token and same-origin `Origin` header | webui → `403` |

nginx always overwrites the `X-SSL-Client-*` headers, and webui listens only on a unix socket that only nginx can reach, so the certificate headers cannot be forged. Responses carry a strict CSP, `no-store`, `X-Frame-Options: DENY`, and `__Host-` cookies.

### Privilege separation

A compromise of the web app yields only the webui container: uid 912, no capabilities, read-only FS, no Docker socket, no host config (only its own `webui.json` and the public CA certs are mounted). The only path to the host is `fabric-agent`:

| Control | Detail |
|---------|--------|
| Socket access | `agent.sock` is `0660 root:<webui gid>` in a `0750` dir; other host users cannot reach it |
| Peer check | `SO_PEERCRED` on every connection: only the webui uid and root are accepted (right group, wrong uid → `403`) |
| Fixed API | `GET /v1/version`, `/v1/services`, `/v1/zones`, `/v1/zones/<key>`, `/v1/audit`, `/v1/pki/ca`, `/v1/pki/issued`, `/v1/tsig`, `/v1/reverse-zones`, `/v1/devices`, `/v1/people`, `/v1/vault`, `/v1/vault/slots`, `/v1/vault/devices`; `POST /v1/zones/<key>/records`, `/v1/zones/<key>/records/delete`, `/v1/apply`, `/v1/events` (`LOGIN`/`LOGOUT`/`LOGIN_DENIED` only), `/v1/pki/{describe-csr,sign,issue,inspect,convert}`, `/v1/tsig`, `/v1/tsig/<name>/{rotate,delete}`, `/v1/devices`, `/v1/devices/<name>`, `/v1/devices/<name>/{delete,certs}`, `/v1/roles`, `/v1/roles/<name>`, `/v1/roles/<name>/delete`. Anything else → `404` |
| Validation | Record input validated in `fabriclib/dns/validate_record.py`; actor must match `^[A-Za-z0-9][A-Za-z0-9._@-]{0,63}$`; body ≤ 64 KiB |
| Audit | Every change is written to `/opt/fabric/archive/audit.log` with the acting user |
| Sandbox | systemd hardening (`NoNewPrivileges`, `ProtectHome`, `ProtectKernel*`, `RestrictNamespaces`, ...); no network listener; IP access limited to localhost + `fabric_subnet` |

---

## Configuration

Enabled by default whenever `install_keycloak: true` (`install_webui` is forced off without Keycloak).

| Variable | Default | Notes |
|----------|---------|-------|
| `install_webui` | `true` | Effective only with Keycloak |
| `webui_hostname` | `fabric.<domain>` | The web UI's address — any host name. Inside the domain a CNAME to this host is added automatically; outside it, point DNS at the host yourself. The certificate and the OIDC redirect follow |
| `cname_mgr` | `fabric` | The default name's label (`<cname_mgr>.<domain>`) when `webui_hostname` is not set |
| `webui_realm` | `domain` | Keycloak realm |
| `webui_admin_role` | `fabric-admin` | Required realm role |
| `webui_admin_group` | `admins` | Group granted the role |
| `webui_admin_user` | account that ran `sudo`, else `fabricadmin` | First admin, created by setup (asked for interactively) |
| `webui_admin_email` | `<user>@<domain>` | Mail attribute of that user (Keycloak's profile needs one) |
| `webui_client_cert_days` | `365` | Lifetime of the admins' client certificates |
| `webui_session_idle` | `900` | Seconds |
| `webui_session_max` | `28800` | Seconds |
| `webui_oidc_secret` | *(generated)* | With fabric's secrets (OpenBao) |

Related: `image_webui` (`fabric/webui:local`), `ip_webui` (`10.255.0.80`), `service_users.webui` (uid/gid `912`) — see [vars.md](vars.md).

After changing the realm/role/group vars: `sudo fabricctl --apply` then `sudo fabricctl --keycloak-sync`.

Image updates: `sudo fabricctl --update-containers` rebuilds the image on a fresh Debian base (`build --pull`). An apply that changes the app code or Dockerfile rebuilds the image; `webui` is always restarted last with `--no-block`, since the apply may have been started from the web UI.

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
5. **Browse** to `https://fabric.<domain>`, pick the certificate, log in with the password from `initial-password.txt`, choose a new password and **enrol TOTP** (scan the QR code with an authenticator app). Later logins ask for the one-time code.

Then delete `initial-password.txt` and `p12-password.txt`.

**More admins:** add the user to `admins` (LDAP, or the Keycloak admin console: *Users → Groups → Join group → admins*), then

```bash
sudo fabricctl client-cert <keycloak-username>
```

which writes `~/fabric-admin/<username>.p12` and shows its password once. `fabricctl --client-cert <user>` is the same command.

Use **Logout** to end both the webui session and the Keycloak session.

---

## Dev preview

To look at the pages without a CA, client certificate, Keycloak or a running install:

```bash
python3 fabric/lib/webui/devserver.py            # from a checkout (needs python3-jinja2) -> http://127.0.0.1:8080
docker run --rm -p 127.0.0.1:8080:8080 --entrypoint /usr/bin/python3 \
    fabric/webui:local /app/webui/devserver.py --bind 0.0.0.0     # from the image, on a fabric host
```

It renders the real pages (`views.py`) with sample data under an orange **DEV PREVIEW** banner. Record edits and Apply work in memory only — there is no fabric-agent, nothing is saved, rendered or reloaded, and a restart resets everything. `/preview/denied` shows a refused sign-in. It is a separate entry point on purpose: the production server (`server.py`) has no dev switch, so a real install can never run without sign-in. It listens on 127.0.0.1 unless told otherwise; never expose it.

## Troubleshooting

| Symptom | Cause / Fix |
|---------|-------------|
| `400 No required SSL certificate was sent` | No client cert presented. Import the `.p12`; restart the browser if it cached "no certificate" for the site. |
| `400 The SSL certificate error` | Cert not from this fabric's CA (or expired). Mint a new one with `fabricctl client-cert <user>`. |
| `403` "client certificate issued by this fabric's certificate authority is required" | Cert chains to the root but was not issued directly by the Step-CA intermediate (e.g. under a sub-CA). |
| `403` "certificate does not belong to this user" | Keycloak username ≠ cert CN. Mint a cert for the exact username. |
| `403` "missing the 'fabric-admin' role" | User not in `admins` (or role mapping drifted). Fix membership, then `sudo fabricctl --keycloak-sync`. |
| `403` "CSRF check failed" | Stale page or cross-origin post. Reload and retry. |
| Login loops / "Login expired" | Login took over 10 min or started in another browser. Start again at `/`. |
| `502 Bad Gateway` | `webui` container not running or socket missing: `systemctl status webui`, `docker ps -a --filter name=webui`, `ls -l /opt/webui/run/`. |
| `503` "fabric-agent service is unavailable" | Agent down or socket missing: `systemctl status fabric-agent`, `journalctl -u fabric-agent -e`, `ls -l /opt/webui/agent/`. |
| `500` / any error | `journalctl -u webui -e` (container), `journalctl -u fabric-agent -e` (agent) |
| Keycloak client/flow missing or wrong | `sudo fabricctl --keycloak-sync` (idempotent) |

Denied logins are recorded as `LOGIN_DENIED` in `/opt/fabric/archive/audit.log`.
