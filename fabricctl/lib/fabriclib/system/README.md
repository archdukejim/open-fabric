# fabriclib/system

| File | What |
|---|---|
| `version_info.py` | Installed fabric version and build stamp (`VERSION` and `BUILD` of the tree it runs from) |
| `service_status.py` | Every installed fabric service: systemd state and container health (for `status` and the web UI) |
| `apply_changes.py` | Render + deploy + reload changed services (`interactive.py --apply`, as `fabricctl --apply`), under the vars lock, audited |
| `control_stack.py` | `fabricctl start/stop/restart/status`: the whole stack through `fabric.target` |
| `render_template_file.py` | `fabricctl --render-jinja`: render one template with fabric's vars, for the caller |
