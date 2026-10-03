from fabriclib.ldap.common.run_dirsrv import run_dirsrv

_READ = r'''
devices = []
for dn, a in c.search_s(DEV, ldap.SCOPE_ONELEVEL, "(objectClass=device)"):
    devices.append({"name": one(a, "cn"), "type": one(a, "fabricDeviceType", "other"),
                    "enabled": one(a, "fabricEnabled", "TRUE").upper() == "TRUE",
                    "macs": s(a.get("macAddress")), "owner": one(a, "owner"),
                    "description": one(a, "description"), "certs": s(a.get("fabricCertFingerprint")),
                    "roles": sorted(s(a.get("fabricRoleName")))})
roles = []
for dn, a in c.search_s(ROLES, ldap.SCOPE_ONELEVEL, "(objectClass=groupOfNames)"):
    roles.append({"name": one(a, "cn"), "description": one(a, "description"),
                  "permissions": s(a.get("fabricPermission")),
                  "vlan": int(one(a, "fabricVlan", "0")) or None, "priority": int(one(a, "fabricPriority", "100"))})
for r in roles:                      # a device names its roles (fabricRoleName); a role lists no members
    r["members"] = sorted(d["name"] for d in devices if r["name"].lower() in {x.lower() for x in d["roles"]})
out({"devices": devices, "roles": roles})
'''


def read_directory(v):
    """Purpose: Every device (this install's, in the local suffix) and device role (the organisation's), raw,
             in one directory read.
    Inputs:  v — fabric vars (run_dirsrv).
    Returns: {"devices": [{name, type, enabled, macs, owner (DN or ""), description, certs (SHA-256
             fingerprints), roles (the role names the device carries, fabricRoleName)}], "roles": [{name,
             description, permissions, vlan (int or None), priority (int, default 100), members (device names,
             computed from the devices' roles)}]}.
    Fails:
             run_dirsrv's errors (ValidationError: password missing, dirsrv not running, "no such
             entry", "that name is already taken", "the directory refused the change ...", "directory
             error: ..."; RuntimeError "directory operation failed: ..."; subprocess.TimeoutExpired).
    Feeds:   add_device, update_device, remove_device, require_device, device_overview, list_devices,
             list_roles.
    """
    return run_dirsrv(v, _READ)
