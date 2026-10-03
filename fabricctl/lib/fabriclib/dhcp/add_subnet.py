from fabriclib.dhcp.common.edit_dhcp import edit_dhcp


def add_subnet(actor, subnet, name, vlan=None, router=None, pools=(), notes="", allow_overlap="", source="cli"):
    """Purpose: add a DHCP subnet with its name, VLAN record, router, pools and notes (design dhcp-management.md
             §4). Applied by the next apply.
    Inputs:  actor — who asks (audit); subnet — network ("192.168.20.0/24"); name — one DNS label, unique;
             vlan — 1-4094 or None (a record: fabric configures no switch); router — address in the subnet or None;
             pools — "first - last" strings; notes — free text (at most 500 characters); allow_overlap — why it
             may overlap another site's network (federation's address plan), "" for none; source — "cli" or "web".
    Returns: the saved subnet (normalized, with its new id: one above the highest in use, never reused while the
             others keep theirs).
    Fails:   ValidationError from normalize_dhcp (bad network, name or vlan taken, pool outside the subnet or
             overlapping another, …) or edit_dhcp (Kea's check; another site's network overlapped); OSError /
             yaml.YAMLError from edit_dhcp.
    Feeds:   run_dhcp_command (add-subnet), agent route POST /v1/dhcp/subnets."""
    def change(dhcp):
        subnets = dhcp.setdefault("subnets", [])
        entry = {"subnet": str(subnet).strip(), "name": name, "id": max([s["id"] for s in subnets] or [0]) + 1,
                 "pools": list(pools), "reservations": []}
        if vlan is not None:
            entry["vlan"] = vlan
        if router:
            entry["routers"] = str(router).strip()
        if notes:
            entry["notes"] = notes
        if allow_overlap:
            entry["allow_overlap"] = allow_overlap
        subnets.append(entry)
        return entry["id"], f"subnet={entry['subnet']} name={name} vlan={vlan} id={entry['id']}"
    sid, dhcp = edit_dhcp(actor, "DHCP_SUBNET_ADD", change, source)
    return next(s for s in dhcp["subnets"] if s["id"] == sid)
