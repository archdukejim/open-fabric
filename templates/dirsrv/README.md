# jinja/dirsrv

389 Directory Server (only with `install_ldap`). Rendered and copied by
`deploy.py` into `/opt/dirsrv/`; the `ldap` systemd unit runs the
`dirsrv` container, and `fabriclib/ldap/seed_directory.py` applies the seed.

| Path | What |
|---|---|
| `docker-compose.yml.j2` | The `dirsrv` container (`image_dirsrv`, default `fabric/dirsrv:local`): ldap uid/gid, `/data` and `/seed` mounts, suffix and Directory Manager password in its environment → `/opt/dirsrv/docker-compose.yml` |
| [`src/containers/dirsrv/seed.py`](../../src/containers/dirsrv/seed.py) | Applies the seed LDIFs idempotently over LDAPI inside the container; prints RESTART_REQUIRED after a cn=config change → copied (not rendered) to `/opt/dirsrv/seed/seed.py` |
| [`packaging/images/dirsrv/`](../../packaging/images/dirsrv/) | The local image: Debian's 389-ds-base with tini and the dscontainer launcher → `/opt/dirsrv/build/` (installed as `build/`) |
| [seed/](seed/) | LDIF templates: server hardening, fabric's schema, tree, accounts, ACIs → `/opt/dirsrv/seed/*.ldif` |
