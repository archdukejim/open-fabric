# fabric library (`fabric/lib/`)

Index of the code behind `fabricctl`, `fabric-agent` and the web UI. New code
follows [AGENTS.md](../AGENTS.md): one operation per file, grouped in domain
folders under `fabric/lib/fabriclib/`, each folder with its own `README.md`
listing its files. The flat files further down predate that rule and are
split as they are touched (see [stale-code register](maintenance/stale-code.md) S6–S7).

## `fabriclib/` — domain code (one operation per file)

| Folder | What | Index |
|---|---|---|
| `fabriclib/common/` | Paths, vars file load/save/lock, audit log, `ValidationError` | [README](../fabric/lib/fabriclib/common/README.md) |
| `fabriclib/dns/` | Zones and records in `vars.yaml` — validated add/remove, zone listing, BIND sync status. The **only** DNS implementation: used by `fabric-agent` (web UI) and the `fabricctl --interactive` editor | [README](../fabric/lib/fabriclib/dns/README.md) |
| `fabriclib/system/` | Version, service status, apply | [README](../fabric/lib/fabriclib/system/README.md) |

## Services and apps

| Path | What |
|---|---|
| `agent/server.py` | `fabric-agent`: root, sandboxed, unix socket only (`/opt/webui/agent/agent.sock`, `0660 root:<webui gid>`, SO_PEERCRED: webui uid + root). Routes a fixed `/v1` API straight to `fabriclib` functions; everything else `404`. See [webui.md](webui.md#privilege-separation). |
| `webui/` | The Fabric web UI, baked into the unprivileged `webui` image: `server.py` (security gates, sessions, CSRF), `oidc.py` (code flow + PKCE, full ID-token verification), `tlsclient.py` (CA-pinned HTTPS), `agentclient.py` (fabric-agent client), `views.py` (autoescaped templates, strict CSP). See [webui.md](webui.md). |
| `keycloak_bootstrap.py` | Idempotent Keycloak setup over the admin API (realm, 389-DS federation, group mapper, `fabric-admin` role, `fabric-webui` client, TOTP flow). `fabricctl --keycloak-sync`, playbook 09. |
| `dirsrv.sh` | 389-DS: wait for health; seed (creates the backend if missing, applies `/seed/*.ldif` idempotently, restarts on `cn=config` change). |
| `ldap_migrate.sh` + `ldap_migrate.py` | One-time OpenLDAP → 389-DS import preserving `entryUUID` (`fabricctl --migrate-ldap`). |

## Legacy flat files (to be split into `fabriclib/`)

| File | What |
|---|---|
| `manage.sh` | `fabricctl` dispatcher: `--interactive`, `--apply`, `--print`, `--update-containers`, `--tsig-keys`/`--list-tsig`/`--remove-tsig`, `--mint-certs`, `--service-cert`, `--client-cert`, `--keycloak-sync`, `--migrate-ldap`, `--render-jinja`, `--version`. |
| `interactive.py` | `--interactive` menus (variables, DNS editor on `fabriclib.dns`, links, cert minting), `--apply` (→ `deploy.py`), `--update-containers` (pull; `build --pull` for `dirsrv`/`webui`). |
| `deploy.py` | Native render + deploy: secrets, templates, compose files, systemd units; restarts only what changed; zones compared ignoring the serial and swapped with `rndc freeze`/`thaw`; 389-DS seed; webui build context; fabric-agent unit. |
| `certs.sh` | `--mint-certs`, `--client-cert` (webui `.p12`, CN = Keycloak user). |
| `services.sh` | `--service-cert`: re-mint nginx-fronted service certs and the 389-DS TLS files. |
| `tsig.sh` | TSIG keys for dynamic DNS (`--tsig-keys`, `--list-tsig`, `--remove-tsig`). |
| `vars.sh` | Comment-preserving YAML list append (`_vars_list_append`) and pre-change backups (`_vars_archive`) used by `certs.sh`/`tsig.sh`. |
| `output.sh` | `info` / `ok` / `warn` / `err` console helpers. |
| `ssh.sh` | Remote install: prepare SSH key access to the target (`setup.sh`). |
| `reinstall_backup.sh` / `reinstall_restore.sh` | `setup.sh --reinstall`: keep CA history and certs across a reinstall (restore runs in playbook 04). |
