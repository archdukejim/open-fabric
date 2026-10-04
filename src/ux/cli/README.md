# src/ux/cli

The CLI's entry points. On a host they sit in `/opt/fabric/lib/` (the command in `/usr/bin/`).

| File | What |
|---|---|
| `fabricctl` | The command (`/usr/bin/fabricctl`): setup and other package commands run from the package, the rest from the install (`manage.sh`) |
| `manage.sh` | The install's side of the `fabricctl` command: hands every argument to `fabriclib/cli.py` (none: the vars editor) |
| `deploy.py` | Entry point of the deploy engine (`fabriclib/deploy/`): `python3 deploy.py` and `--apply` (setup calls the engine directly) |
| `interactive.py` | Entry point of `fabricctl --interactive`, `--print` and `--apply` (`fabriclib/menu/`); the web UI's apply runs `interactive.py --apply` |
| `keycloak_bootstrap.py` | Entry point of the Keycloak configuration (`fabriclib/keycloak/configure_keycloak.py`); imports the web UI's TLS client |
