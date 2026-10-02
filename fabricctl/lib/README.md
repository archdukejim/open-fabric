# fabricctl/lib

| Path | What |
|---|---|
| [fabriclib/](fabriclib/) | fabric's Python library, one operation per file, grouped by domain (imported as `fabriclib.<domain>.<file>`); `fabriclib/cli.py` routes the `fabricctl` subcommands |
| [agent/](agent/) | `fabric-agent`: the root daemon behind the web UI — a fixed, permission-checked JSON API over a unix socket |
| [federation/](federation/) | `fabric-federation`: the federation endpoint sites join through (behind nginx, unix socket) |
| `deploy.py` | Entry point of the deploy engine (`fabriclib/deploy/`): `python3 deploy.py` and `--apply` (setup calls the engine directly) |
| `interactive.py` | `fabricctl --interactive` (menu-driven vars editor), `--print` (list the vars) and `--apply` (run the deploy engine; also what the web UI's apply runs) (predates one-function-per-file) |
| `keycloak_bootstrap.py` | Entry point of the Keycloak configuration (`fabriclib/keycloak/configure_keycloak.py`) |
| `manage.sh` | The install's side of the `fabricctl` command: hands every argument to `fabriclib/cli.py` (none: the vars editor) |
| `README.md` | This file |

`webui/` (the web UI, from the repository's `webui/`) is added here by the
package; the Keycloak configuration imports its TLS client from it.
