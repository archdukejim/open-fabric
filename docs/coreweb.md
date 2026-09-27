# core-web Management UI

core-web is a browser front end for `core-mgr`. It runs on the host as systemd service `coreweb` and is reachable only through nginx at `https://mgr.<domain>` (`hostname_mgr`).

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
| Dashboard (`/`) | `systemctl is-active` status of `nginx`, `bind9`, `stepca`, `ldap`, `postgres`, `keycloak`, `coreweb`; zone list; version/build |
| Zone (`/zone/<zone>`) | View records (A, AAAA, CNAME, MX, TXT, SRV); add or delete a record in `vars.yaml` |
| Apply | Runs the same apply as `sudo core-mgr --apply` (`interactive.py --apply`) and shows its output |
| Audit (`/audit`) | Last 200 lines of `/opt/core/archive/audit.log` (logins, denials, record edits, applies) |

Record edits only change `vars.yaml`; nothing is published until **Apply**. Edits and applies take a lock file (`/opt/core/config/.coreweb.lock`) so concurrent web sessions do not interleave.

---

## Components

| Item | Location |
|------|----------|
| Code | `/opt/core/lib/coreweb/` (`server.py`, `oidc.py`, `tlsclient.py`, `actions.py`, `views.py`; stdlib + `jinja2`/`pyyaml`) |
| Config | `/opt/coreweb/coreweb.json` (root, `0600`; contains the OIDC client secret) — from `core/jinja/coreweb/coreweb.json.j2` |
| Unit | `/etc/systemd/system/coreweb.service` — from `core/jinja/systemd/coreweb.service.j2` (runs as root, sandboxed; IP access limited to localhost + `core_net`) |
| Socket | `/opt/coreweb/run/web.sock` (dir `root:nginx 0750`), mounted into nginx at `/srv/coreweb` |
| nginx vhost | `server_name hostname_mgr`; `ssl_verify_client on`, `ssl_verify_depth 2`, trust `/opt/nginx/certs/client-ca/ca-bundle.pem` (intermediate + root) |
| Server cert | `mgr.<domain>` offline Step-CA leaf, minted by playbook 08 |
| Keycloak | realm `coreweb_realm`, client `core-mgr`, role `core-admin`, flow `core-mgr-browser-mfa` — created by `keycloak_bootstrap.py` |

---

## Security Model

Every request must pass all gates:

| # | Gate | Enforced by |
|---|------|-------------|
| 1 | TLS client certificate that chains to the core root CA within depth 2 | nginx (`ssl_verify_client on`) — no cert → `400` |
| 2 | Certificate issued **directly** by the Step-CA intermediate (leaves under a subordinate CA are rejected) | core-web (issuer DN check) → `403` |
| 3 | Keycloak login: OIDC authorization code + PKCE (S256); ID token signature, issuer, audience, azp, expiry and nonce verified | core-web + Keycloak |
| 4 | TOTP second factor (flow `core-mgr-browser-mfa`, bound to the `core-mgr` client only) | Keycloak |
| 5 | Keycloak username **equals** the client certificate CN | core-web → `403` |
| 6 | User holds realm role `coreweb_admin_role` (default `core-admin`, granted to LDAP group `coreweb_admin_group`, default `admins`) | core-web → `403` |
| 7 | Session bound to the certificate fingerprint; idle timeout 15 min, max 8 h | core-web (session dropped → re-login) |
| 8 | State-changing requests are POST-only with a per-session CSRF token and same-origin `Origin` header | core-web → `403` |

nginx always overwrites the `X-SSL-Client-*` headers, and core-web listens only on a unix socket that only nginx can reach, so the certificate headers cannot be forged. Responses carry a strict CSP, `no-store`, `X-Frame-Options: DENY`, and `__Host-` cookies.

---

## Configuration

Enabled by default whenever `install_keycloak: true` (`install_coreweb` is forced off without Keycloak).

| Variable | Default | Notes |
|----------|---------|-------|
| `install_coreweb` | `true` | Effective only with Keycloak |
| `cname_mgr` / `hostname_mgr` | `mgr` / `mgr.<domain>` | CNAME is added to the zone automatically |
| `coreweb_realm` | `domain` | Keycloak realm |
| `coreweb_admin_role` | `core-admin` | Required realm role |
| `coreweb_admin_group` | `admins` | Group granted the role |
| `coreweb_session_idle` | `900` | Seconds |
| `coreweb_session_max` | `28800` | Seconds |
| `coreweb_oidc_secret` | *(generated)* | In `core-secrets.yml` |

After changing the realm/role/group vars: `sudo core-mgr --apply` then `sudo core-mgr --keycloak-sync`.

---

## First-Time Setup

1. **Keycloak user in `admins`.** Make sure your user exists in LDAP and is a member of `cn=admins,ou=groups,<base_dn>` (or add it in the Keycloak admin console: *Users → Groups → Join group → admins*). Group membership grants `core-admin`.
2. **Mint a client certificate** on the core host. `<username>` must be the exact Keycloak username:
   ```bash
   sudo core-mgr --client-cert <username>
   ```
   You are asked for a password; the result is `~/<username>-core-mgr.p12` (mode `0600`). The private key exists only inside the `.p12`.
3. **Import the `.p12`** into your browser (or OS certificate store) using that password. The core root CA must also be trusted — see `https://<domain>/` or `https://ca.<domain>/pki/`.
4. **Browse** to `https://mgr.<domain>` and select the certificate when prompted.
5. **Sign in** to Keycloak and **enrol TOTP** on first login (scan the QR code with an authenticator app). Later logins ask for the one-time code.

Use **Logout** to end both the core-web session and the Keycloak session.

---

## Troubleshooting

| Symptom | Cause / Fix |
|---------|-------------|
| `400 No required SSL certificate was sent` | No client cert presented. Import the `.p12`; restart the browser if it cached "no certificate" for the site. |
| `400 The SSL certificate error` | Cert not from this core's CA (or expired). Mint a new one with `--client-cert`. |
| `403` "client certificate issued by this core's certificate authority is required" | Cert chains to the root but was not issued directly by the Step-CA intermediate (e.g. under a sub-CA). |
| `403` "certificate does not belong to this user" | Keycloak username ≠ cert CN. Mint a cert for the exact username. |
| `403` "missing the 'core-admin' role" | User not in `admins` (or role mapping drifted). Fix membership, then `sudo core-mgr --keycloak-sync`. |
| `403` "CSRF check failed" | Stale page or cross-origin post. Reload and retry. |
| Login loops / "Login expired" | Login took over 10 min or started in another browser. Start again at `/`. |
| `502 Bad Gateway` | `coreweb` not running or socket missing: `systemctl status coreweb`, `ls -l /opt/coreweb/run/`. |
| `500` / any error | `journalctl -u coreweb -e` |
| Keycloak client/flow missing or wrong | `sudo core-mgr --keycloak-sync` (idempotent) |

Denied logins are recorded as `LOGIN_DENIED` in `/opt/core/archive/audit.log`.
