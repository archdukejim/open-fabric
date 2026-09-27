# webui Management UI

webui is a browser front end for `fabricctl`. It runs as an unprivileged container (`webui`, systemd service `webui`) and is reachable only through nginx at `https://mgr.<domain>` (`hostname_mgr`). Every read and change it makes goes through `fabric-agent`, a small privileged host service with a fixed JSON API on a unix socket.

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

| Page | What it does |
|------|--------------|
| Dashboard (`/`) | `systemctl is-active` status of `nginx`, `bind9`, `stepca`, `ldap`, `postgres`, `keycloak`, `webui`, `fabric-agent`; zone list; version/build |
| Zone (`/zone/<zone>`) | View records (A, AAAA, CNAME, MX, TXT, SRV); add or delete a record in `vars.yaml` |
| Apply | fabric-agent runs the same apply as `sudo fabricctl --apply` (`interactive.py --apply`); the output is shown |
| Audit (`/audit`) | Last 200 lines of `/opt/fabric/archive/audit.log` (logins, denials, record edits, applies) |

Record edits only change `vars.yaml`; nothing is published until **Apply**. Edits and applies take a lock file (`/opt/fabric/config/.webui.lock`) so concurrent web sessions do not interleave.

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
| Server cert | `mgr.<domain>` offline Step-CA leaf, minted by playbook 08 |
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
| Fixed API | `GET /v1/version`, `/v1/services`, `/v1/zones`, `/v1/zones/<key>`, `/v1/audit`; `POST /v1/zones/<key>/records`, `/v1/zones/<key>/records/delete`, `/v1/apply`, `/v1/events` (`LOGIN`/`LOGOUT`/`LOGIN_DENIED` only). Anything else → `404` |
| Validation | Record input validated in `fabriclib/dns/validate_record.py`; actor must match `^[A-Za-z0-9][A-Za-z0-9._@-]{0,63}$`; body ≤ 64 KiB |
| Audit | Every change is written to `/opt/fabric/archive/audit.log` with the acting user |
| Sandbox | systemd hardening (`NoNewPrivileges`, `ProtectHome`, `ProtectKernel*`, `RestrictNamespaces`, ...); no network listener; IP access limited to localhost + `fabric_subnet` |

---

## Configuration

Enabled by default whenever `install_keycloak: true` (`install_webui` is forced off without Keycloak).

| Variable | Default | Notes |
|----------|---------|-------|
| `install_webui` | `true` | Effective only with Keycloak |
| `cname_mgr` / `hostname_mgr` | `mgr` / `mgr.<domain>` | CNAME is added to the zone automatically |
| `webui_realm` | `domain` | Keycloak realm |
| `webui_admin_role` | `fabric-admin` | Required realm role |
| `webui_admin_group` | `admins` | Group granted the role |
| `webui_session_idle` | `900` | Seconds |
| `webui_session_max` | `28800` | Seconds |
| `webui_oidc_secret` | *(generated)* | In `fabric-secrets.yml` |

Related: `image_webui` (`fabric/webui:local`), `ip_webui` (`10.255.0.80`), `service_users.webui` (uid/gid `912`) — see [vars.md](vars.md).

After changing the realm/role/group vars: `sudo fabricctl --apply` then `sudo fabricctl --keycloak-sync`.

Image updates: `sudo fabricctl --update-containers` rebuilds the image on a fresh Debian base (`build --pull`). An apply that changes the app code or Dockerfile rebuilds the image; `webui` is always restarted last with `--no-block`, since the apply may have been started from the web UI.

---

## First-Time Setup

1. **Keycloak user in `admins`.** Make sure your user exists in LDAP and is a member of `cn=admins,ou=groups,<base_dn>` (or add it in the Keycloak admin console: *Users → Groups → Join group → admins*). Group membership grants `fabric-admin`.
2. **Mint a client certificate** on the core host. `<username>` must be the exact Keycloak username:
   ```bash
   sudo fabricctl --client-cert <username>
   ```
   You are asked for a password; the result is `~/<username>-fabricctl.p12` (mode `0600`). The private key exists only inside the `.p12`.
3. **Import the `.p12`** into your browser (or OS certificate store) using that password. The core root CA must also be trusted — see `https://<domain>/` or `https://ca.<domain>/pki/`.
4. **Browse** to `https://mgr.<domain>` and select the certificate when prompted.
5. **Sign in** to Keycloak and **enrol TOTP** on first login (scan the QR code with an authenticator app). Later logins ask for the one-time code.

Use **Logout** to end both the webui session and the Keycloak session.

---

## Troubleshooting

| Symptom | Cause / Fix |
|---------|-------------|
| `400 No required SSL certificate was sent` | No client cert presented. Import the `.p12`; restart the browser if it cached "no certificate" for the site. |
| `400 The SSL certificate error` | Cert not from this fabric's CA (or expired). Mint a new one with `--client-cert`. |
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
