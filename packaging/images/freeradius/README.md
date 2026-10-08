# jinja/freeradius/build

Build context of the local image `fabric/freeradius:local`, copied (not
rendered) to `/opt/freeradius/build/` by `deploy.py`; rebuilt when it changes
or its base differs (`fabriclib/images/needs_rebuild.py`).

| File | What |
|---|---|
| `Dockerfile` | Debian's freeradius, freeradius-python3, python3-ldap and winbind (`ntlm_auth`, PEAP) on `BASE_IMAGE` (pinned `image_debian`), stock sites/mods removed, fabric's freerad uid/gid; label `org.fabric.base` |
