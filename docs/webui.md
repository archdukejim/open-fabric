# webui Management UI

webui is a browser front end for `fabricctl`. It runs on the host as systemd service `webui` and is reachable only through nginx at `https://mgr.<domain>` (`hostname_mgr`).

### Table of Contents
- [Features](#features)
- [Components](#components)
- [Security Model](#security-model)
- [Configuration](#configuration)
- [First-Time Setup](#first-time-setup)
- [Troubleshooting](#troubleshooting)

---

## Features

| Page | What it does |
|------|--------------|
| Dashboard (`/`) | `systemctl is-active` status of `nginx`, `bind9`, `stepca`, `ldap`, `postgres`, `keycloak`, `webui`; zone list; version/build |
| Zone (`/zone/<zone>`) | View records (A, AAAA, CNAME, MX, TXT, SRV); add or delete a record in `vars.yaml` |
| Apply | Runs the same apply as `sudo fabricctl --apply` (`interactive.py --apply`) and shows its output |
| Audit (`/audit`) | Last 200 lines of `/opt/fabric/archive/audit.log` (logins, denials, record edits, applies) |

Record edits only change `vars.yaml`; nothing is published until **Apply**. Edits and applies take a lock file (`/opt/fabric/config/.webui.lock`) so concurrent web sessions do not interleave.

---

## Components

| Item | Location |
|------|----------|
| Code | `/opt/fabric/lib/webui/` (`server.py`, `oidc.py`, `tlsclient.py`, `actions.py`, `views.py`; stdlib + `jinja2`/`pyyaml`) |
| Config | `/opt/webui/webui.json` (root, `0600`; contains the OIDC client secret) — from `fabric/jinja/webui/webui.json.j2` |
| Unit | `/etc/systemd/system/webui.service` — from `fabric/jinja/systemd/webui.service.j2` (runs as root, sandboxed; IP access limited to localhost + `fabric_net`) |
| Socket | `/opt/webui/run/web.sock` (dir `root:nginx 0750`), mounted into nginx at `/srv/webui` |
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

After changing the realm/role/group vars: `sudo fabricctl --apply` then `sudo fabricctl --keycloak-sync`.

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
| `502 Bad Gateway` | `webui` not running or socket missing: `systemctl status webui`, `ls -l /opt/webui/run/`. |
| `500` / any error | `journalctl -u webui -e` |
| Keycloak client/flow missing or wrong | `sudo fabricctl --keycloak-sync` (idempotent) |

Denied logins are recorded as `LOGIN_DENIED` in `/opt/fabric/archive/audit.log`.
