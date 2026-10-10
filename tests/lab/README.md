# tests/lab

Suites on the Hyper-V lab (manual 2.3.1.9.6): real machines on an isolated switch, no router, never the house's LAN.

| File | What |
|---|---|
| `dhcp.sh` | DHCP beyond the host's LAN (manual 1.10.3.8, the gate for 0.8): fabric serving its second interface; real Ubuntu clients get a lease from the pool, fabric's DNS and a route to `host_ip`, their name and PTR, fabric's pages by name; a reservation; a guest subnet DNS only; off and on again from `fabricctl dhcp`; doctor |
