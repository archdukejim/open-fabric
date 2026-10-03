# fabriclib/ldap/common

Helpers shared by the device and role operations.

| File | What |
|---|---|
| `run_dirsrv.py` | Run a directory snippet in the dirsrv container as `cn=device_admin` (password and input via env); LDAP refusals become `ValidationError` |
| `read_directory.py` | All devices and device roles, raw, in one call |
| `check_device_fields.py` | Validate a device's type, MACs (unique across devices), owner, description, roles |
| `check_role_fields.py` | Validate a role's permissions, VLAN, priority, description |
| `normalize_mac.py` | Any common MAC spelling → `aa:bb:cc:dd:ee:ff`; refuses multicast |
