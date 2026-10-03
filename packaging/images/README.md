# packaging/images

One folder per image fabric builds; each is a build context (`Dockerfile` and what it copies). On a host they are
installed as `jinja/<service>/build/`.

| Path | What |
|---|---|
| [adguard/](adguard/) | AdGuard Home |
| [bind9/](bind9/) | BIND 9 from Debian packages |
| [dirsrv/](dirsrv/) | 389 Directory Server from Debian packages |
| [freeradius/](freeradius/) | FreeRADIUS |
| [kea/](kea/) | Kea DHCP 3.0 from ISC's repository (decision D22) |
| [keycloak/](keycloak/) | Keycloak's optimized build |
| [stepca/](stepca/) | Step-CA |
| [webui/](webui/) | The Open Fabric web UI |
