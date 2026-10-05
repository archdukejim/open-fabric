# fabriclib/ldap/common

Helpers shared by the device and role operations.

| File | What |
|---|---|
| `run_dirsrv.py` | Run a directory snippet in the dirsrv container as `cn=device_admin` (password and input via env); LDAP refusals become `ValidationError` |
