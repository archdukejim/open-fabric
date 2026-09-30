import json
import threading

import ldap
import ldap.filter

CONFIG = "/etc/freeradius/fabric/fabric-radius.json"
_local = threading.local()
_conf = {}


def _load():
    if not _conf:
        with open(CONFIG) as f:
            _conf.update(json.load(f))
        with open(_conf["password_file"]) as f:
            _conf["password"] = f.read().strip()
    return _conf


def _connect():
    conf = _load()
    c = ldap.initialize(conf["uri"])
    c.set_option(ldap.OPT_X_TLS_CACERTFILE, conf["ca_file"])
    c.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_DEMAND)
    c.set_option(ldap.OPT_X_TLS_NEWCTX, 0)
    # short: a switch waits a few seconds; the directory down must still answer Reject in time
    c.set_option(ldap.OPT_NETWORK_TIMEOUT, 2)
    c.set_option(ldap.OPT_TIMEOUT, 3)
    c.set_option(ldap.OPT_REFERRALS, 0)
    c.simple_bind_s(conf["bind_dn"], conf["password"])
    return c


def _search(base, filterstr, attrs):
    """One search on this thread's connection; reconnects once if 389-DS
    restarted since. Any other LDAP error propagates (the caller refuses)."""
    for attempt in (1, 2):
        c = getattr(_local, "conn", None)
        try:
            if c is None:
                c = _local.conn = _connect()
            return c.search_s(base, ldap.SCOPE_ONELEVEL, filterstr, attrs)
        except (ldap.SERVER_DOWN, ldap.CONNECT_ERROR, ldap.TIMEOUT):
            _local.conn = None
            if attempt == 2:
                raise


def _vals(attrs, key):
    return [v.decode() for v in attrs.get(key) or []]


def lookup_device(attribute, value, permission):
    """The device whose `attribute` (fabricCertFingerprint or macAddress)
    is `value`, judged for `permission`: {device, allowed, vlan, reason}.
    device is None if no device (or more than one) has that value. Access is
    the union of the device's roles' permissions, nothing while it is
    disabled; the VLAN comes from the lowest-priority-number role that sets
    one (ties by name) — the same rules as the web UI (list_devices)."""
    conf = _load()
    devices = _search("ou=devices," + conf["base"],
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
    for _, a in _search("ou=device-roles," + conf["base"],
                        "(&(objectClass=groupOfNames)(member=%s))" % ldap.filter.escape_filter_chars(dn),
                        ["cn", "fabricPermission", "fabricVlan", "fabricPriority"]):
        roles.append({"name": (_vals(a, "cn") or [""])[0], "permissions": _vals(a, "fabricPermission"),
                      "vlan": int((_vals(a, "fabricVlan") or ["0"])[0]) or None,
                      "priority": int((_vals(a, "fabricPriority") or ["100"])[0])})
    if not any(permission in r["permissions"] for r in roles):
        return {"device": name, "allowed": False, "vlan": None, "reason": f"no role grants {permission}"}
    vlan_role = next((r for r in sorted(roles, key=lambda r: (r["priority"], r["name"])) if r["vlan"]), None)
    return {"device": name, "allowed": True, "vlan": vlan_role["vlan"] if vlan_role else None, "reason": ""}
