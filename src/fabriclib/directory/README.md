# fabriclib/directory

fabric's directory on Samba AD (manual 1.6.3, 2.11.2.16): what fabric-agent, setup and the web UI ask of it. Every
operation runs inside the DC (`src/containers/samba/directory_op.py`), signed in as this site's `fabric-agent`
account, so AD's per-site limits apply to it.

| File | What |
|---|---|
| `__init__.py` | Package marker |
| `run_op.py` | Run one directory operation as the site's agent account; refusals as messages safe to show |
| `list_people.py` | The People page: every person and group (never a password) and the Keycloak console link |
| `create_person.py` | A new person in this site (POSIX identity from its block, `<site>-users`, a one-time password) |
| `reset_sign_in.py` | A new one-time password in AD; TOTP removed and sessions ended in Keycloak (fabric groups: admins only) |
| `ensure_admin.py` | Setup's first admin: made once, kept in the web UI's admin group |
| `people_password.py` | A one-time password the domain's policy accepts |
