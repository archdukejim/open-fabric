# fabriclib/system

| File | What |
|---|---|
| `version_info.py` | Installed fabric version (`fabric/VERSION`) and build stamp (`fabric/BUILD`) |
| `service_status.py` | `systemctl is-active` for every fabric service that is installed |
| `apply_changes.py` | Render + deploy + reload changed services (same as `fabricctl --apply`), locked and audited |
| `control_stack.py` | `fabricctl start/stop/restart/status`: the whole stack through `fabric.target` |
