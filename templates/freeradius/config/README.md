# jinja/freeradius/config

FreeRADIUS configuration, rendered by `fabriclib/radius/deploy_freeradius.py`
to `/opt/freeradius/config/<name>` (root:freerad 0640) and mounted read-only
at `/etc/freeradius/fabric`. `deploy_freeradius` also writes `ldap-password`
(the `cn=radius_reader` password) here.

| Path | What |
|---|---|
| `radiusd.conf.j2` | Main configuration: fabric's own minimal tree, logs to the journal (decisions, never passwords) → `radiusd.conf` |
| `clients.conf.j2` | RADIUS clients (switches, APs) with their secrets from fabric's secrets; Message-Authenticator required unless relaxed → `clients.conf` |
| `fabric-radius.json.j2` | For the policy: 389-DS URI (LDAPS, verified), CA file, reader account and password file, base DN, groups mapped for password logins → `fabric-radius.json` |
| [mods/](mods/) | Modules: `always`, `eap`, `fabric_policy` → `mods/` |
| [sites/](sites/) | Virtual servers: `fabric`, `check-eap-tls`, `inner-tunnel` → `sites/` |
