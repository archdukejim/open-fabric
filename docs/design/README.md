# docs/design

| File | What |
|---|---|
| `fabricctl-package.md` | The product design and every decision (D1–D25) |
| `image-updates.md` | Automated image validation and the host side (D21) |
| `federation.md` | Sites, upstream/downstream and HA partners: attachment (flat, relay, nested), joining, DNS between sites, phases and the build plan, open decisions (being built) |
| `dns-filter.md` | An optional DNS filter (AdGuard Home) in front of BIND, per site: settings, what fabric generates, OIDC sign-in, federation (milestone M7, being built) |
| `dhcp-management.md` | DHCP subnets, pools, any DHCP option (PXE, ZTP), client classes, VLAN/name/notes records, and the address plan across federated sites (milestone M8, planned) |
| `ntp.md` | Time for the site and its network: chrony on the host, NTS sources, the federation hierarchy, serving the LAN, checks (milestone M9, planned) |
