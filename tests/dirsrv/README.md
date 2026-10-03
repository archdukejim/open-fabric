# tests/dirsrv

| File | What |
|---|---|
| `run.sh` | 389-DS on fabric's image with fabric's seed: healthy as uid 911, seeding idempotent, TLS-only binds (plaintext and TLS < 1.2 refused), anonymous reads without passwords, ACIs, memberOf, the admin user, the one-time passwords fabric generates always passing the password policy (a weak one refused), device RBAC |
| `admin_user.py` | Setup's admin step (`ensure_admin_user`) against the test directory |
| `devices.py` | Device and role operations as `cn=device_admin`, like fabric-agent: validation and its refusals, effective permissions and VLAN, certificate links, least privilege, the audit log |
| `posix.py` | POSIX identities against real 389-DS: the DNA plugin's numbers from the users range, unique, never reused; unsafe names skipped; idempotent |
| `migrate.py` | Upgrade from before the directory split: old-layout devices, role members and service accounts moved to the local suffix; a second run changes nothing |
