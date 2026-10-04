# fabriclib/deploy

The deploy engine (`fabricctl --apply`, the web UI's Apply, setup's `deploy` step), split out of the old
`lib/deploy.py` (which is now only its entry point). One run renders every template into `/tmp/fabric-render`,
installs what changed and restarts or reloads what is affected.

| File | What |
|---|---|
| `apply_deployment.py` | The engine: the steps below in order; every refusal is an `Error: …` line and exit 1 |
| `deploy_paths.py` | Where it reads and writes, from the environment at call time (deploy base, vars, secrets, link vars) |
| `generate_missing_secrets.py` | fabric's own secrets that do not exist yet, created once |
| `merge_tsig_keys.py` | TSIG keys and ACL policies from the vars, checked; each key's secret kept or generated |
| `merge_radius_clients.py` | 802.1X clients and groups from the vars, checked; each client's shared secret kept, generated or removed |
| `render_vars.py` | `vars.yaml.j2` rendered over the admin's vars and the secrets (the full settings); the RAM minimum |
| `archive_vars.py` | Keep the deployed `vars.yaml` in `archive/` before it is replaced |
| `check_fixed_identity.py` | `site_name`, `org_domain` and `ldap_base_dn` valid and unchanged since install (the markers in `config/`) |
| `check_settings.py` | DHCP, time and `dns_filter` settings checked before anything is rendered |
| `load_link_vars.py` | The landing page's links, rendered into the context (a bad file is reported, never fatal) |
| `service_units.py` | fabric's container services and their wrapper units, with which are on |
| `render_templates.py` | Every configuration file into the render folder |
| `install_fabric_tree.py` | fabric itself, the secrets file, vars, link vars, web pages and the manual's docs |
| `install_service_units.py` | Each service's compose file, image build context and systemd wrapper; which to restart or rebuild |
| `install_openbao_config.py` | OpenBao's folders and config |
| `install_nginx_config.py` | nginx's config and `fabric.target` |
| `install_bind9_files.py` | BIND's folders and config; the zones whose records changed |
| `install_dirsrv_seed.py` | 389-DS's seed files |
| `install_webui_files.py` | The web UI's folders and config; fabric-agent's unit |
| `install_stepca_templates.py` | Step-CA's certificate templates |
| `install_directory_sync_timer.py` | The timer giving people created in Keycloak's console their POSIX identity |
| `install_runtime_dirs.py` | Data folders services write; each TSIG key's `rfc2136.ini` |
| `deploy_optional_parts.py` | Fluent Bit, the DNS filter, chrony, Kea, FreeRADIUS through their own deploy steps |
| `finish_without_start.py` | Setup's ending: start nothing, swap zones safely, build images, return what to restart |
| `restart_changed.py` | Apply's ending: build images, restart and reload what changed, the web UI last |
| `verify_published_images.py` | Before anything is installed: the signature of every published fabric image this deploy runs (D81, D85) |
| `compose_builds.py` | Whether a rendered compose file builds its image or pulls it (published images are pulled) |
