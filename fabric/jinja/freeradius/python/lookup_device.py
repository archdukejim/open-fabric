import ldap.filter

from directory import load_config, search


def _vals(attrs, key):
    return [v.decode() for v in attrs.get(key) or []]


def lookup_device(attribute, value, permission):
    """The device whose `attribute` (fabricCertFingerprint or macAddress)
    is `value`, judged for `permission`: {device, allowed, vlan, reason}.
    device is None if no device (or more than one) has that value. Access is
    the union of the device's roles' permissions, nothing while it is
    disabled; the VLAN comes from the lowest-priority-number role that sets
    one (ties by name) — the same rules as the web UI (list_devices)."""
    conf = load_config()
    devices = search("ou=devices," + conf["base"],
                      "(&(objectClass=device)(%s=%s))" % (attribute, ldap.filter.escape_filter_chars(value)),
                      ["cn", "fabricEnabled"])
    if len(devices) != 1:
        return {"device": None, "allowed": False, "vlan": None,
                "reason": "no device has it" if not devices else "more than one device has it"}
    dn, attrs = devices[0]
    name = (_vals(attrs, "cn") or ["?"])[0]
    if (_vals(attrs, "fabricEnabled") or ["TRUE"])[0].upper() != "TRUE":
        return {"device": name, "allowed": False, "vlan": None, "reason": "device disabled"}
    roles = []
    for _, a in search("ou=device-roles," + conf["base"],
                        "(&(objectClass=groupOfNames)(member=%s))" % ldap.filter.escape_filter_chars(dn),
                        ["cn", "fabricPermission", "fabricVlan", "fabricPriority"]):
        roles.append({"name": (_vals(a, "cn") or [""])[0], "permissions": _vals(a, "fabricPermission"),
                      "vlan": int((_vals(a, "fabricVlan") or ["0"])[0]) or None,
                      "priority": int((_vals(a, "fabricPriority") or ["100"])[0])})
    if not any(permission in r["permissions"] for r in roles):
        return {"device": name, "allowed": False, "vlan": None, "reason": f"no role grants {permission}"}
    vlan_role = next((r for r in sorted(roles, key=lambda r: (r["priority"], r["name"])) if r["vlan"]), None)
    return {"device": name, "allowed": True, "vlan": vlan_role["vlan"] if vlan_role else None, "reason": ""}
