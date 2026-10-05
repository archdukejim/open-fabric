# fabriclib/ldap

389 Directory Server operations. They run inside the `dirsrv` container over
LDAPI; inputs travel as environment variables, never argv. Setup binds as
Directory Manager. Devices and roles have moved to AD (`fabriclib/directory`);
what is left here goes in S7 (manual 2.11.2.12).

| File | What |
|---|---|
| `list_people.py` | Users and groups, read-only (managed in Keycloak), and the Keycloak console URL |
| `migrate_local_suffix.py` | Move an install from before the directory split: devices and service accounts to the local suffix |
| `ensure_posix_identities.py` | Give every person without one a POSIX identity (uidNumber assigned by 389-DS's DNA plugin from the users range, group `users`, `/home/<uid>`) |
| `people_written_here.py` | Whether people are written on this install (standalone or root site) or arrive from upstream |
| `common/` | `run_dirsrv`, for what is left here (see its README) |
| `run_directory_command.py` | `fabricctl directory sync` |
| `seed_directory.py` | Seed 389-DS: create the suffix backends on first run, apply the seed LDIFs, restart once if `cn=config` changed |
| `ensure_admin_user.py` | Create a user under `ou=users,ou=accounts` if missing (never changes an existing one) and add it to the web UI admin group |
