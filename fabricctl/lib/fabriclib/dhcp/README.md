# fabriclib/dhcp

Optional DHCP with Kea 3.0 LTS (design §5, D16, D22): `dhcp:` in
`vars.yaml` is the source of truth; lease hostnames go to their own dynamic
zone `dhcp.<domain>` through kea-dhcp-ddns.

| File | What |
|---|---|
| `normalize_dhcp.py` | Check `dhcp:` before anything is rendered: interfaces, subnets, pools, routers, reservations, lease time, no static record inside a pool |
| `deploy_kea.py` | Kea's config files (root:kea 0640), its leases and control-socket folders, and the DHCP zone |
| `ensure_ddns_zone.py` | Create the empty dynamic zone file `db.<sub>.<domain>` once; never rewritten |
| `kea_command.py` | Send one command to kea-dhcp4's control socket; raise on an error result |
| `list_leases.py` | Active leases from Kea (lease_cmds hook) |
| `dhcp_overview.py` | What the Kea tab and `fabricctl dhcp` show: on/off, subnets, reservations, DHCP zone, leases |
| `add_reservation.py` | Reserve an address for a MAC (optionally with a hostname) in `vars.yaml`, validated, audited |
| `remove_reservation.py` | Remove a MAC's reservation from `vars.yaml`, audited |
| `run_dhcp_command.py` | `fabricctl dhcp status / leases / reserve / unreserve` |
