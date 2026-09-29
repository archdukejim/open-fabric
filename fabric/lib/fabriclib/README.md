# fabriclib

fabric's own Python code, grouped by domain; one operation per file
(see [AGENTS.md](../../../AGENTS.md) §2). Run with `fabric/lib` on `sys.path`
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
| [logs/](logs/) | Optional log forwarding (Fluent Bit): config, credentials, status |
| [images/](images/) | Container images: status against the validated list, update (health-gated, rollback), prune |

`cli.py` routes the lifecycle commands (`fabricctl setup|doctor|uninstall|reinstall`).
