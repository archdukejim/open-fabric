# fabriclib/dhcp

Optional DHCP with Kea 3.0 LTS (design §5, 2.1.4.1, 2.1.1.5): `dhcp:` in
`vars.yaml` is the source of truth; lease hostnames go to their own dynamic
zone `dhcp.<domain>` through kea-dhcp-ddns.

| File | What |
|---|---|
| `normalize_dhcp.py` | Check `dhcp:` before anything is rendered: interfaces, subnets (stable ids, name, VLAN, notes), pools (inside, not overlapping), routers, options, reservations, lease time, no static record inside a pool |
| `normalize_options.py` | Check a list of DHCP options (name or code, data, space, flags) at any level |
| `normalize_option_defs.py` | Check `dhcp.option_defs` (options Kea has no name for) |
| `normalize_client_classes.py` | Check `dhcp.client_classes` (Kea expression, options, network-boot fields) |
| `kea_option_data.py` | Kea's option-data for one level: fabric's own options, the admin's replacing them by name |
| `kea_option_defs.py` | Kea's option-def list |
| `kea_client_classes.py` | Kea's client-classes list |
| `check_kea_config.py` | Kea's own check (`kea-dhcp4 -t`) of a configuration before it is saved or installed |
| `add_subnet.py` | Add a subnet (name, VLAN record, router, pools, notes) with the next id |
| `update_subnet.py` | Change a subnet's name, VLAN, router, notes or pools (its network and id stay) |
| `remove_subnet.py` | Remove a subnet (refused with active leases unless forced; the others keep their ids) |
| `set_option.py` | Set any option for every subnet, a subnet, a client class or a reservation |
| `unset_option.py` | Remove an option the admin set |
| `add_client_class.py` | Add a client class (Kea expression, next-server, boot file) |
| `remove_client_class.py` | Remove a client class and its options |
| `common/` | Helpers shared by the commands: the checked edit of `dhcp:`, finding a subnet, where an option goes |
| `deploy_kea.py` | Kea's config files (root:kea 0640, both checked by Kea before either is written), its leases and control-socket folders, and the DHCP zone |
| `ensure_ddns_zone.py` | Create the empty dynamic zone file `db.<sub>.<domain>` once; never rewritten |
| `kea_command.py` | Send one command to kea-dhcp4's control socket; raise on an error result |
| `list_leases.py` | The leases Kea holds (lease_cmds hook, `lease4-get-all`), with state and expiry |
| `dhcp_overview.py` | What the Kea tab and `fabricctl dhcp` show: on/off, subnets, reservations, DHCP zone, leases |
| `add_reservation.py` | Reserve an address for a MAC (optionally with a hostname) in `vars.yaml`, whole `dhcp:` revalidated (locked, audited) |
| `remove_reservation.py` | Remove a MAC's reservation from `vars.yaml` (locked, audited) |
| `run_dhcp_command.py` | `fabricctl dhcp status / leases / reserve / unreserve / add-subnet / set-subnet / remove-subnet / option / class` (applies after a change unless `--no-apply`) |
