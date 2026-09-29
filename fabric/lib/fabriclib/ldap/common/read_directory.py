from fabriclib.ldap.common.run_dirsrv import run_dirsrv

_READ = r'''
devices = []
for dn, a in c.search_s(DEV, ldap.SCOPE_ONELEVEL, "(objectClass=device)"):
    devices.append({"name": one(a, "cn"), "type": one(a, "fabricDeviceType", "other"),
                    "enabled": one(a, "fabricEnabled", "TRUE").upper() == "TRUE",
                    "macs": s(a.get("macAddress")), "owner": one(a, "owner"),
                    "description": one(a, "description"), "certs": s(a.get("fabricCertFingerprint"))})
roles = []
for dn, a in c.search_s(ROLES, ldap.SCOPE_ONELEVEL, "(objectClass=groupOfNames)"):
    roles.append({"name": one(a, "cn"), "description": one(a, "description"),
                  "permissions": s(a.get("fabricPermission")),
                  "vlan": int(one(a, "fabricVlan", "0")) or None, "priority": int(one(a, "fabricPriority", "100")),
                  "members": [m.split(",", 1)[0][3:] for m in s(a.get("member")) if m.lower().endswith(DEV.lower())]})
out({"devices": devices, "roles": roles})
'''


def read_directory(v):
    """Every device and device role, raw ({devices, roles}); owners as DNs,
    role members as device names."""
    return run_dirsrv(v, _READ)
