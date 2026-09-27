# fabriclib

fabric's own Python code, grouped by domain; one operation per file
(see [AGENTS.md](../../../AGENTS.md) §2). Run with `fabric/lib` on `sys.path`
and import as `fabriclib.<domain>.<file>`.

| Folder | What |
|---|---|
| [common/](common/) | Shared helpers: paths, vars file, locking, audit log, errors |
| [dns/](dns/) | DNS zones and records in `vars.yaml` (validated), zone sync status |
| [system/](system/) | Version, service status, apply |
