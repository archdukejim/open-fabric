# fabricctl/lib

| Path | What |
|---|---|
| [fabriclib/](fabriclib/) | fabric's Python library, one operation per file, grouped by domain (imported as `fabriclib.<domain>.<file>`) |
| [agent/](agent/) | `fabric-agent`: the root daemon behind the web UI — a fixed, permission-checked API over a unix socket |
| `deploy.py` | The deploy engine: render every template from `vars.yaml` and apply the changes (predates one-function-per-file: split when touched) |
| `interactive.py` | `fabricctl --interactive`: the menu-driven editor (predates one-function-per-file) |
| `keycloak_bootstrap.py` | Configure Keycloak idempotently: realm, LDAP federation, web UI client, roles (predates one-function-per-file) |
| `manage.sh` | `/opt/fabric` side of the `fabricctl` command: routes every subcommand |
| `certs.sh` | Shell helpers for extra certificates (`fabricctl --mint-certs`) |
| `dirsrv.sh` | 389-DS helpers: seed the directory (`bash dirsrv.sh seed`) |
| `vars.sh` | Shell helpers that edit `vars.yaml` lists |
| `output.sh` | Coloured output for the shell helpers |

`webui/` (the web UI, from the repository's `webui/`) is added here by the
package.
