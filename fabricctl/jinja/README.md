# fabricctl/jinja

Templates rendered by `deploy.py` (and `fabriclib`) from `vars.yaml` into
`/opt/<service>/` (systemd units into `/etc/systemd/system/`). One folder per service; `build/` folders are the local
image layers built on the pinned base images.

| Path | What |
|---|---|
| `vars.yaml.j2` | Every setting with its default; rendered over the admin's `vars.yaml` |
| [bind9/](bind9/) | Authoritative DNS: named.conf parts, zones, image |
| [dirsrv/](dirsrv/) | 389 Directory Server: image, seed LDIF (server config, schema, tree, accounts, ACIs) and `seed.py` |
| [fluentbit/](fluentbit/) | Optional log forwarding |
| [adguard/](adguard/) | Optional DNS filter: AdGuard Home in front of BIND, its configuration and oauth2-proxy's |
| [adguard-auth/](adguard-auth/) | The DNS filter's sign-in (oauth2-proxy), a unit of its own |
| [chrony/](chrony/) | Time on the host (chrony's configuration; not a container) |
| [freeradius/](freeradius/) | Optional 802.1X: config, image and fabric's policy code |
| [kea/](kea/) | Optional DHCP: Kea configs and image |
| [keycloak/](keycloak/) | SSO: compose file and image |
| [nginx/](nginx/) | Reverse proxy and the static pages: landing, certificates, LDAP guide, manual |
| [openbao/](openbao/) | Secrets: compose file and server config |
| [postgres/](postgres/) | Keycloak's database |
| [stepca/](stepca/) | The CA: compose file, image, certificate templates |
| [systemd/](systemd/) | The per-service wrapper unit, `fabric.target`, `fabric-agent.service` |
| [webui/](webui/) | Deploying the web UI container: compose file and `webui.json` (its image is built from the repository's `webui/`) |
