# AI Test Plan: fabric Deployment

**Deployment Domain:** `<domain>`
**Host IP:** `<host_ip>`
**LAN CIDR:** `<lan_cidr>`

This document outlines the testing strategy for an AI agent to execute, validate, and troubleshoot the deployment of the `fabric` infrastructure in offline or standard environments.

## 1. Environment Preparation
- [ ] Verify execution environment is Ubuntu 24.04.
- [ ] Ensure the AI has `sudo` access or operates as `root`.
- [ ] Verify network connectivity and DNS resolution.
- [ ] Capture existing networking configuration (e.g., `ip a`, `resolvectl status`, `cat /etc/resolv.conf`) to ensure proper rollback if execution fails.
- [ ] Variables in `custom-vars.yaml` have been correctly rendered.

## 2. Full Installation Test
- [ ] **Action**: `sudo apt install ./fabricctl_<v>_all.deb`, then `sudo fabricctl setup --file vars.yaml --non-interactive --yes` (automated: `tests/sandbox/run.sh`, a disposable systemd + Docker sandbox with no checkout inside).
- [ ] **Expected**:
  - Every setup step completes and setup prints `fabric is ready`; `sudo fabricctl doctor` passes; a second `sudo fabricctl setup` converges without re-issuing certificates; no secret appears in any process's argv.
  - Docker containers `nginx`, `bind9`, `step-ca` (and optionally `dirsrv`, `keycloak`, `postgres`, `webui`) are healthy.
  - If Keycloak is enabled, `systemctl is-active webui fabric-agent` reports `active` for both.
  - The `verify` step's LDAP/webui checks pass (role-account binds, plaintext bind refused, LDAPS cert verifies, agent socket `0660` with webui gid, webui returns `400` without a client cert).
- [ ] **Validation**: 
  - `docker ps` shows all containers running.
  - `nslookup dns.<domain> localhost -port=<bind_dns_port>` returns the host IP.
  - `curl -kI https://ca.<domain>` returns an HTTP response indicating step-ca is up.
  - `sudo fabricctl --version` prints the version from `fabric/VERSION` and the build stamp (commit + time).

## 3. Subfunctionality Tests

### 3.1 DNS and Zone Updates
- [ ] **Action**: Modify A/CNAME records in `custom-vars.yaml` or via `fabricctl`.
- [ ] **Action**: Run `sudo fabricctl --apply`.
- [ ] **Expected**: `fabricctl` detects DNS changes, re-renders templates, and updates only the changed zones (freeze → swap file → drop `.jnl` → thaw) without restarting the container. Re-running `--apply` with no record changes touches no zone.
- [ ] **Validation**: Use `dig` to confirm the new records resolve correctly; `fabricctl --interactive` → DNS shows the zone `IN SYNC` and lists CNAME/MX/TXT/SRV values.

### 3.2 PKI / Bring Your Own Certs (BYOC)
- [ ] **Action**: Conduct a teardown (`sudo ./setup.sh --uninstall --force`) to prepare a clean environment.
- [ ] **Action**: Generate an offline Root CA, set `byoc: true` and specify paths in `custom-vars.yaml`.
- [ ] **Action**: Run `sudo ./setup.sh --file vars.yaml --non-interactive --yes` (automated: `tests/sandbox/run.sh`, a disposable systemd + Docker sandbox).
- [ ] **Expected**: Step-CA imports the offline CA and starts successfully.
- [ ] **Validation**: Inspect `/opt/stepca/data/certs/` to confirm the BYOC intermediate cert is present.

### 3.3 Dynamic Configuration Updates
- [ ] **Action**: Modify a setting in `custom-vars.yaml` (e.g., timezone, domain).
- [ ] **Action**: Run `sudo fabricctl --apply`.
- [ ] **Expected**: Configuration templates are re-rendered and only affected services are restarted or reloaded.

### 3.4 LDAP (389 Directory Server)
- [ ] **Action**: `LDAPTLS_CACERT=/opt/stepca/data/certs/root_ca.crt ldapwhoami -H ldaps://ldap.<domain> -x -D "cn=super_admin,ou=admins,ou=accounts,<base_dn>" -W` (password: `sudo fabricctl secrets show ldap_super_admin_password`).
- [ ] **Expected**: Bind succeeds on 636, and on 389 with `-ZZ`; the same bind on 389 **without** `-ZZ` is refused.
- [ ] **Action**: Anonymous `ldapsearch -ZZ -H ldap://ldap.<domain> -x -b <base_dn> "(uid=*)" uid uidNumber userPassword`.
- [ ] **Expected**: POSIX attributes are returned; `userPassword` is never returned.

### 3.5 webui
- [ ] **Action**: `curl --cacert /opt/stepca/data/certs/root_ca.crt https://fabric.<domain>/` without a client certificate.
- [ ] **Expected**: HTTP `400` from nginx.
- [ ] **Action**: use the login kit setup wrote to `~/fabric-admin/` (automated: `tests/sandbox/login_test.py`, run by `tests/sandbox/run.sh`): trust the root CA, import the `.p12`, browse to `https://fabric.<domain>`, log in with `initial-password.txt`.
- [ ] **Expected**: Keycloak asks for a new password and TOTP enrolment, then the dashboard; the initial password no longer works afterwards. A user without `fabric-admin`, or a cert whose CN differs from the username, gets `403`. Actions appear in `/opt/fabric/archive/audit.log`.
- [ ] **Action**: `sudo systemctl stop fabric-agent`, reload the dashboard, then `sudo systemctl start fabric-agent`.
- [ ] **Expected**: `503` "fabric-agent service is unavailable" while stopped; dashboard works again after start.
- [ ] **Action**: Step-CA tab (automated: `sudo tests/run-all.sh pki webui`): make a CSR on a device (`openssl req -new -newkey rsa:2048 -nodes -keyout d.key -out d.csr -subj /CN=dev.<domain> -addext subjectAltName=DNS:dev.<domain>`), upload it under **Sign a CSR**, review, sign; generate a key + certificate under **New key + certificate**; inspect and convert the results.
- [ ] **Expected**: the certificates verify against `certs.<domain>/ca-chain.pem` with the requested names and validity. A 1024-bit key, a tampered CSR or a URI name are refused. Validity above `pki_manual_max_days` is refused. The `.p12` opens with the shown password. **Issued** lists both certificates. `issued-certs.jsonl` holds no keys.
- [ ] **Action**: BIND9 → TSIG keys → create a key for the zone (listed hosts), put the `rfc2136.ini` into a certbot client, Apply, run a DNS-01 challenge.
- [ ] **Expected**: the challenge succeeds for the listed hosts only. After **New secret** + Apply the old secret is refused.

### 3.6 webui Isolation
- [ ] **Action**: Inspect the container: `docker inspect webui`, `docker exec webui id`, `docker exec webui sh -c 'grep Cap /proc/self/status'`.
- [ ] **Expected**: uid/gid `912` (`service_users.webui`), `CapEff` all zero, `ReadonlyRootfs: true`, `no-new-privileges`, no published ports, no `/var/run/docker.sock`, only `/config`, `/certs`, `/run/webui`, `/agent` (+ tmpfs `/tmp`) mounted; writing to `/` or `/agent` fails; host config (`/opt/fabric`, `vars.yaml`, `stepca/data/secrets`) not visible.
- [ ] **Action**: As another host user, and as a process with the webui gid but a different uid, connect to `/opt/webui/agent/agent.sock`.
- [ ] **Expected**: Other users get permission denied; the wrong uid with the right group is rejected (`403`, `SO_PEERCRED`).
- [ ] **Action**: From the container, request a path outside the agent API (e.g. `GET /v1/exec`, `GET /`).
- [ ] **Expected**: `404`.

### 3.6b OpenBao
- [ ] **Action**: `sudo fabricctl vault status`; reboot the host; run it again (automated: `sudo tests/run-all.sh openbao hardening sandbox`).
- [ ] **Expected**: `unsealed (static seal, raft storage)` both times with nobody entering a key; `~/fabric-admin/openbao-recovery-keys.txt` exists once (0600); `/etc/fabric/openbao/slots.json` is `0600 root`, the key-file method `local-fabric-1.key` `0400 root`, and nothing is left in `/run/fabric/openbao/`; `https://vault.<domain>/ui/` loads with the fabric CA trusted.
- [ ] **Action**: move `local-fabric-1.key` away and restart `openbao`; restore it and restart; `sudo fabricctl vault rotate --yes`.
- [ ] **Expected**: sealed and *unhealthy* while missing (DNS, LDAP, SSO, nginx keep working); unsealed with all data after the restore; `fabricctl setup` refuses to create a new key while data exists.

### 3.7 RFC2136 with an existing TSIG key
- [ ] **Action**: give `tsig_keys: [{name: npm, records: [npm], secret: <existing>}]` in the vars; after setup, point nginx-proxy-manager (certbot `rfc2136`) at `host_ip:53` with that key (automated: `tests/sandbox/rfc2136_test.sh`).
- [ ] **Expected**: the certificate is issued; `nsupdate` with the key sets `_acme-challenge.npm.<domain>` TXT; other names and wrong secrets are refused; the secret is only in fabric's secrets (`fabricctl secrets show tsig/npm`); a setup re-run keeps it.
