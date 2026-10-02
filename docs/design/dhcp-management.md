# Design: DHCP management — subnets, pools, options, client classes, address plan

Status: **planned** (owner request 2026-10-01). Milestone M8 of
[federation.md](federation.md) §8a, built before M5; the address plan rides
on M5's site-to-upstream sync and is shown in M6's Federation tab.

## 1. Why

Today only reservations have commands and web UI controls; subnets and pools
are edited in `vars.yaml`, and Kea gets a fixed set of options (DNS servers,
domain, search list, routers). The owner wants to manage subnets and pools
from fabric, keep a record of what each VLAN is for, set **any** DHCP option
(PXE, switch ZTP, NTP, vendor options), and — with federation — see every
site's networks in one place so addresses never collide.

## 2. Settings

```yaml
dhcp:
  options:                            # every subnet (Kea's global option-data)
    - { name: ntp-servers, data: 192.168.4.2 }
  option_defs:                        # options Kea has no name for
    - { name: ztp-url, code: 239, type: string }
  client_classes:                     # match clients, give them their own options
    - name: pxe-uefi
      test: "option[93].hex == 0x0007"
      options:
        - { name: tftp-server-name, data: 192.168.4.30 }
        - { name: boot-file-name, data: ipxe.efi }
    - name: arista-ztp
      test: "substring(option[60].hex,0,6) == 'Arista'"
      options: [ { name: ztp-url, data: "http://192.168.4.30/ztp/bootstrap" } ]
  subnets:
    - subnet: 192.168.20.0/24
      name: iot                       # unique per site; 802.1X roles can name it
      vlan: 20                        # a record (1–4094, unique per site): fabric does not configure switches
      notes: "IoT: internet only, trunked on switch1 port 24"
      pools: ["192.168.20.100 - 192.168.20.200"]
      routers: 192.168.20.1
      options: [ { name: domain-name-servers, data: 192.168.20.1 } ]   # override for this subnet
      reservations:
        - { mac: "aa:bb:cc:dd:ee:ff", ip: 192.168.20.20, hostname: cam1,
            options: [ { name: boot-file-name, data: cam.bin } ] }
```

An option is `{name | code, data, space (default dhcp4), csv_format, always_send}` — Kea's own
`option-data`, at global, class, subnet and reservation level (most specific wins, as in Kea).

## 3. Safety

- Rendered with `to_json`, never by string pasting; names, codes (1–254), spaces and types validated.
- Options fabric sets itself (DNS, domain, search list, routers) may be overridden per subnet; the
  overrides are shown in status.
- Every change runs Kea's own check (`kea-dhcp4 -t` on the new file) before it is installed; a refused
  file is never applied and the error is shown.
- Pools: inside their subnet, not overlapping each other, no reservation or static A record inside one
  (as today). Removing a subnet with active leases needs `--force`.
- `notes` is free text (length-limited), shown HTML-escaped.

## 4. Commands and web UI

```
fabricctl dhcp add-subnet 192.168.20.0/24 --name iot --vlan 20 --router 192.168.20.1 --pool "a - b" --notes "…"
fabricctl dhcp set-subnet iot --vlan 20 --notes "…" | --add-pool "a - b" | --remove-pool "a - b"
fabricctl dhcp remove-subnet iot [--force]
fabricctl dhcp option set|unset [--subnet iot | --class pxe-uefi | --mac …] <name|code> [<data>]
fabricctl dhcp class add|remove …
```

The Kea tab gets the same (permission `dhcp:write`). A device role's or mapped group's VLAN shows the
subnet it belongs to ("VLAN 20 (iot, 192.168.20.0/24)").

## 5. Address plan across sites (with M5/M6)

- Each site reports its networks — `lan_cidr`, every DHCP subnet with name, VLAN and notes — to its
  upstream at join and on every change; the root and relays keep the whole plan with each network's
  site, and every site keeps a copy (works while the upstream is away).
- Overlaps are refused at join and on every subnet change, naming the other site's network; an explicit
  `--allow-overlap <reason>` for networks that are never routed together. Changes made offline are
  re-checked when the link returns and conflicts flagged on both sites.
- `fabric_subnet` is checked against every real network too (the same on every site and harmless
  there, but a LAN using it would be unreachable from that site's containers).
- `fabricctl federation networks`; the Federation tab (M6) shows site → network → VLAN → notes.

## 6. Not in scope

Serving the boot or ZTP files themselves (a TFTP/HTTP boot service could be a later optional
component); DHCPv6; configuring switches from the VLAN records.
