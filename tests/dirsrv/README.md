# tests/dirsrv

| File | What |
|---|---|
| `run.sh` | 389-DS on fabric's image with fabric's seed: healthy as uid 911, seeding idempotent, TLS-only binds, ACIs, memberOf, the admin user, device RBAC |
| `admin_user.py` | Setup's admin step (`ensure_admin_user`) against the test directory |
| `devices.py` | Device and role operations as `cn=device_admin`, like fabric-agent |
