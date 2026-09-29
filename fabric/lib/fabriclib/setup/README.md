# fabriclib/setup

`fabricctl setup` — install or re-converge fabric on this host. Every step is idempotent and can run alone:
`sudo fabricctl setup --step <name>`; `--list` shows them in order.

| File | What |
|---|---|
| `run_setup.py` | CLI for `fabricctl setup` / `doctor`: options, input, plan, runs the steps |
| `steps.py` | The ordered step list |
| `context.py` | `SetupContext`: install paths, rendered vars, secrets, options, services to restart |
| `errors.py` | `SetupError` — a step cannot continue; message says why and what to do |
| `collect_vars.py` | Where settings come from: existing install, `--file` (or a checkout's `custom-vars.yaml` on a fresh install) overrides, prompts for anything missing |
| `upgrade_vars.py` | Existing install's vars before re-render: new release's images (unless pinned) |
| `detect_network.py` | Guess hostname, host IP, gateway and LAN CIDR from the default route |
| `choose_plan.py` | Show the (hardened) default plan; Proceed / Advanced / Quit |
| `preflight.py` | Architecture, OS, RAM, cgroup memory controller, conflicting listeners |
| `condition_host.py` | Host packages and Docker Engine (compose v2, buildx) |
| `harden_docker.py` | Hardened `/etc/docker/daemon.json` (merged, not replaced) |
| `deploy_config.py` | Render + deploy all configuration without starting anything; install `fabricctl` |
| `create_accounts.py` | Service users and groups with the expected uid/gid |
| `configure_network.py` | Docker network `fabric_net`; optional host resolver drop-in |
| `configure_firewall.py` | UFW default-deny (SSH from the LAN) + LAN-only Docker-published ports; lockout guard |
| `init_pki.py` | Step-CA init (own root or bring-your-own), `ca.json`, CA certs published and trusted |
| `start_bootstrap.py` | Start bind9 + step-ca; validate every zone |
| `mint_service_certs.py` | Issue/renew service certificates (only what is missing, expiring or wrong) |
| `mint_extra_certs.py` | `extra_certs` entries, when missing or due (part of the `certs` step) |
| `start_services.py` | Start the stack in order; seed 389-DS; configure Keycloak; fabric-agent + web UI |
| `start_unit.py` | Enable, start or restart one unit and wait until its container is healthy |
| `setup_openbao.py` | `vault` step: seal key, start OpenBao, init once (recovery keys to `~/fabric-admin`, root token used once and revoked), converge its configuration, move fabric's secrets file into OpenBao |
| `create_admin.py` | First web UI admin: LDAP user in the admin group, forced password change, client `.p12`, root CA and README in `~/fabric-admin` |
| `verify_install.py` | End-to-end checks (DNS, HTTPS chains, LDAPS, role binds, plaintext refused, web UI gates, services) |
| `uninstall.py` | Remove fabric (only fabric's own objects) |
| `backup_install.py` | Keep config, secrets, CA, certificates and OpenBao (data + seal key) for a reinstall (owners preserved) |
| `restore_install.py` | Put that backup back before setup runs |
| `stage_source.py` | Reinstall from the installed copy: stage the code in `/var/tmp` so uninstall cannot delete what setup runs from |
| `renew_service_certs.py` | `fabricctl certs [--force]`: day-2 renewal; restarts only services whose certs changed |
