from fabriclib.ldap.common.read_directory import read_directory


def list_devices(v, directory=None):
    """Devices with their roles and what those roles add up to: effective
    permissions (union of all roles; none while disabled) and VLAN (from
    the lowest-priority-number role that sets one). Owner as a username."""
    directory = directory or read_directory(v)
    out = []
    for d in sorted(directory["devices"], key=lambda d: d["name"]):
        roles = sorted((r for r in directory["roles"] if d["name"] in r["members"]),
                       key=lambda r: (r["priority"], r["name"]))
        perms = sorted({p for r in roles for p in r["permissions"]}) if d["enabled"] else []
        vlan_role = next((r for r in roles if r["vlan"]), None)
        owner = d["owner"].split(",", 1)[0].partition("=")[2] if d["owner"] else ""
        out.append({**d, "owner": owner, "roles": [r["name"] for r in roles], "permissions": perms,
                    "vlan": vlan_role["vlan"] if vlan_role and d["enabled"] else None,
                    "vlan_from": vlan_role["name"] if vlan_role else ""})
    return out
