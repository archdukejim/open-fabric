# fabriclib/dhcp/common

Helpers shared by the DHCP commands.

| File | What |
|---|---|
| `edit_dhcp.py` | One checked change to `dhcp:` in vars.yaml: locked, normalized (ids stored), checked by Kea before it is saved, audited |
| `find_subnet.py` | The subnet a command names, by name or network |
| `option_target.py` | Where an option goes: every subnet, a subnet, a client class or a reservation |
