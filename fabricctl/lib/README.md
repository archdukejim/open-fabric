# fabricctl/lib

| Path | What |
|---|---|
| [fabriclib/](fabriclib/) | fabric's Python library, one operation per file, grouped by domain (imported as `fabriclib.<domain>.<file>`); `fabriclib/cli.py` routes the `fabricctl` subcommands |
| [agent/](agent/) | `fabric-agent`: the root daemon behind the web UI — a fixed, permission-checked JSON API over a unix socket |
| [federation/](federation/) | `fabric-federation`: the federation endpoint sites join through (behind nginx, unix socket) |
| `deploy.py` | The deploy engine (`apply_deployment`): render every template from `vars.yaml` and the secrets, deploy what changed, reload/restart what is affected; used by `fabricctl setup` and `--apply` (predates one-function-per-file: split when touched) |
| `interactive.py` | `fabricctl --interactive` (menu-driven vars editor), `--print` (list the vars) and `--apply` (run `deploy.py`; also what the web UI's apply runs) (predates one-function-per-file) |
| `keycloak_bootstrap.py` | Configure Keycloak idempotently: realm, LDAP federation and group sync, permission roles, TOTP flow, `fabric-webui` and `fabric-openbao` clients; its `Admin` client is reused by `fabriclib/keycloak/` (predates one-function-per-file) |
| `manage.sh` | `/opt/fabric` side of the `fabricctl` command: hands the lifecycle subcommands to `fabriclib/cli.py` and handles the flag modes (`--mint-certs`, `--service-cert`, `--render-jinja`, `--print`, `--interactive`, `--apply`, `--client-cert`, `--keycloak-sync`, `--version`) |
| `certs.sh` | Shell side of `fabricctl --mint-certs` (extra certificates) and `--service-cert` (re-issue service certificates) |
| `dirsrv.sh` | 389-DS helpers: wait for health, seed the directory (`bash dirsrv.sh seed`) |
| `vars.sh` | Shell helpers for `vars.yaml`: append to a list, archive a copy before a change |
| `output.sh` | Coloured output (`info`, `ok`, `warn`, `err`) and `usage` for the shell helpers |
| `README.md` | This file |

`webui/` (the web UI, from the repository's `webui/`) is added here by the
package; `deploy.py` and `keycloak_bootstrap.py` import from it.
