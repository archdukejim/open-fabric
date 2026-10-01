# fabriclib

fabric's own Python code, grouped by domain; one operation per file
(see [AGENTS.md](../../../AGENTS.md) §2). Run with `fabricctl/lib` on `sys.path`
and import as `fabriclib.<domain>.<file>`.

| Folder | What |
|---|---|
| [common/](common/) | Shared helpers: paths, vars file, locking, audit log, errors |
| [dns/](dns/) | DNS zones and records in `vars.yaml` (validated), zone sync status |
| [system/](system/) | Version, service status, apply |
| [setup/](setup/) | `fabricctl setup`, `doctor`, `uninstall`, `reinstall` — the installer |
| [pki/](pki/) | Issue, check and install certificates from Step-CA |
| [security/](security/) | Firewall for Docker-published ports |
| [rbac/](rbac/) | Access control for people: permissions, bundles, what each fabric-agent route needs |
| [dhcp/](dhcp/) | Optional DHCP (Kea 3.0): `dhcp:` checks, config, DDNS zone, reservations, leases, `fabricctl dhcp` |
| [radius/](radius/) | Optional 802.1X (FreeRADIUS): RADIUS clients and their secrets, config, decisions log, `fabricctl radius` |
| [logs/](logs/) | Optional log forwarding (Fluent Bit): config, credentials, status |
| [images/](images/) | Container images: status against the validated list, update (health-gated, rollback), prune |
| [keycloak/](keycloak/) | Keycloak over its admin REST API: people, sign-in resets, roles, token checks, the OpenBao OIDC client |
| [ldap/](ldap/) | 389 Directory Server over LDAPI inside `dirsrv`: devices, device roles, certificate links, people and roles lists, admin user |
| [vault/](vault/) | OpenBao: init, configure, status, unlock methods (key slots: USB, security key, KMIP), vault key rotation, root token |
| [secrets/](secrets/) | fabric's own secrets: the 0600 file until the vault step, then OpenBao; load, save, import, export |
| [federation/](federation/) | Sites: the site-name rule; invitations, joining and the federation endpoint as they are built |

`cli.py` routes the `fabricctl` commands implemented here (setup, doctor, uninstall, reinstall, certs, tsig, acl,
dhcp, radius, vault, logs, images, …) to one function each; `__init__.py` is empty (package marker).
