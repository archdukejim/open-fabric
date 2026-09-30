# fabriclib/ldap

389 Directory Server operations. They run inside the `dirsrv` container over
LDAPI; inputs travel as environment variables, never argv. Setup binds as
Directory Manager; the device and role operations (web UI) bind as the
least-privilege `cn=device_admin`, so the directory's ACIs limit them.

| File | What |
|---|---|
| `constants.py` | Device types, the permission vocabulary (what it grants, what enforces it), name rules, the default device roles |
| `device_overview.py` | Devices (with effective access), roles and the vocabulary from one directory read |
| `list_devices.py` | Devices with their roles, effective permissions and VLAN |
| `list_roles.py` | Device roles by priority, with their member devices |
| `add_device.py` | Add a device and put it in its roles (audited) |
| `update_device.py` | Change a device's type, MACs, owner, description, enabled flag and roles (audited) |
| `remove_device.py` | Delete a device and take it out of every role (audited) |
| `require_device.py` | Refuse unless a device exists (before issuing a certificate for it) |
| `link_device_cert.py` | Record or forget a certificate fingerprint on a device (audited) |
| `add_role.py` | Create a device role: permissions, VLAN, priority (audited) |
| `update_role.py` | Change a role's permissions, VLAN, priority, description (audited) |
| `remove_role.py` | Delete a role — refused while devices are in it (audited) |
| `list_people.py` | Users and groups, read-only (managed in Keycloak), and the Keycloak console URL |
| `common/` | Helpers shared by the operations above (see its README) |
| `ensure_default_device_roles.py` | Create the default device roles once (a marker file keeps a deleted one from coming back) |
| `ensure_admin_user.py` | Create a user under `ou=users,ou=accounts` if missing (never changes an existing one) and add it to the web UI admin group |
