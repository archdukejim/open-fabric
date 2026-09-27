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
- [ ] **Action**: Run `sudo ./setup.sh`.
- [ ] **Expected**:
  - Playbooks 00-10 complete successfully without failure.
  - Docker containers `nginx`, `bind9`, `step-ca` (and optionally `dirsrv`, `keycloak`, `postgres`, `webui`) are healthy.
  - If Keycloak is enabled, `systemctl is-active webui fabric-agent` reports `active` for both.
  - Playbook 10 LDAP/webui checks pass (role-account binds, plaintext bind refused, LDAPS cert verifies, agent socket `0660` with webui gid, webui returns `400` without a client cert).
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
- [ ] **Action**: Run `sudo ./setup.sh`.
- [ ] **Expected**: Step-CA imports the offline CA and starts successfully.
- [ ] **Validation**: Inspect `/opt/stepca/data/certs/` to confirm the BYOC intermediate cert is present.

### 3.3 Dynamic Configuration Updates
- [ ] **Action**: Modify a setting in `custom-vars.yaml` (e.g., timezone, domain).
- [ ] **Action**: Run `sudo fabricctl --apply`.
- [ ] **Expected**: Configuration templates are re-rendered and only affected services are restarted or reloaded.

### 3.4 LDAP (389 Directory Server)
- [ ] **Action**: `LDAPTLS_CACERT=/opt/stepca/data/certs/root_ca.crt ldapwhoami -H ldaps://ldap.<domain> -x -D "cn=super_admin,ou=admins,ou=accounts,<base_dn>" -W` (password: `ldap_super_admin_password` from `fabric-secrets.yml`).
- [ ] **Expected**: Bind succeeds on 636, and on 389 with `-ZZ`; the same bind on 389 **without** `-ZZ` is refused.
- [ ] **Action**: Anonymous `ldapsearch -ZZ -H ldap://ldap.<domain> -x -b <base_dn> "(uid=*)" uid uidNumber userPassword`.
- [ ] **Expected**: POSIX attributes are returned; `userPassword` is never returned.

### 3.5 webui
- [ ] **Action**: `curl --cacert /opt/stepca/data/certs/root_ca.crt https://mgr.<domain>/` without a client certificate.
- [ ] **Expected**: HTTP `400` from nginx.
- [ ] **Action**: `sudo fabricctl --client-cert <user>` for a Keycloak user in LDAP group `admins`; import the `.p12`; browse to `https://mgr.<domain>`.
- [ ] **Expected**: Keycloak login with TOTP enrolment/prompt, then the dashboard. A user without `fabric-admin`, or a cert whose CN differs from the username, gets `403`. Actions appear in `/opt/fabric/archive/audit.log`.
- [ ] **Action**: `sudo systemctl stop fabric-agent`, reload the dashboard, then `sudo systemctl start fabric-agent`.
- [ ] **Expected**: `503` "fabric-agent service is unavailable" while stopped; dashboard works again after start.

### 3.6 webui Isolation
- [ ] **Action**: Inspect the container: `docker inspect webui`, `docker exec webui id`, `docker exec webui sh -c 'grep Cap /proc/self/status'`.
- [ ] **Expected**: uid/gid `912` (`service_users.webui`), `CapEff` all zero, `ReadonlyRootfs: true`, `no-new-privileges`, no published ports, no `/var/run/docker.sock`, only `/config`, `/certs`, `/run/webui`, `/agent` (+ tmpfs `/tmp`) mounted; writing to `/` or `/agent` fails; host config (`/opt/fabric`, `vars.yaml`, `stepca/data/secrets`) not visible.
- [ ] **Action**: As another host user, and as a process with the webui gid but a different uid, connect to `/opt/webui/agent/agent.sock`.
- [ ] **Expected**: Other users get permission denied; the wrong uid with the right group is rejected (`403`, `SO_PEERCRED`).
- [ ] **Action**: From the container, request a path outside the agent API (e.g. `GET /v1/exec`, `GET /`).
- [ ] **Expected**: `404`.

### 3.7 OpenLDAP Migration (upgrade from < 1.5.0 only)
- [ ] **Action**: With `/opt/openldap` from an old install present, run `sudo fabricctl --migrate-ldap`.
- [ ] **Expected**: Entries imported into 389-DS, group members merged, `cn=admin` dropped; a migrated user can log in to Keycloak with their old password. Re-running reports everything as skipped.

## 4. Teardown
- [ ] **Action**: Run `sudo ./setup.sh --uninstall --force`.
- [ ] **Expected**: All containers, networks, and directories in `/opt/` are destroyed.
- [ ] **Validation**: `docker ps -a` shows no fabric containers; `ls /opt/fabric` fails; `systemctl status fabric-agent` reports the unit not found; `id webui` fails.
