# fabriclib/directory/common

Helpers shared by the device, role and people operations.

| File | What |
|---|---|
| `read_directory.py` | This site's devices and the device roles it may use, raw, in one call (operation `read_devices`) |
| `check_device_fields.py` | Validate a device's type, MACs (unique across devices), owner, description, roles |
| `check_role_fields.py` | Validate a role's permissions, VLAN, priority, description |
| `normalize_mac.py` | Any common MAC spelling → `aa:bb:cc:dd:ee:ff`; refuses multicast |
| `person_guard.py` | Who may change a person's sign-in: fabric groups only by an admin, never yourself, never the last admin |
