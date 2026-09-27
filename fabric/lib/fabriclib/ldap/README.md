# fabriclib/ldap

389 Directory Server operations. They run inside the `dirsrv` container over
LDAPI as Directory Manager; inputs travel as environment variables, never argv.

| File | What |
|---|---|
| `ensure_admin_user.py` | Create a user under `ou=users,ou=accounts` if missing (never changes an existing one) and add it to the web UI admin group |
