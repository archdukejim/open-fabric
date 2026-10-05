from fabriclib.directory.common.read_directory import read_directory


def list_devices(v, directory=None):
    """Purpose: Devices with their roles and what those roles add up to.
    Inputs:  v — fabric vars (used only when directory is not given); directory — optional read_directory
             result, default a fresh read.
    Returns: list sorted by name of read_directory's device dicts with "owner" as a username and "roles"
             (names, by priority), "permissions" (union of the roles; [] while disabled), "vlan" (from the
             lowest-priority-number role that sets one; None while disabled), "vlan_from" (that role or "").
    Fails:   read_directory's /
             run_dirsrv's errors (ValidationError: password missing, dirsrv not running, "no such
             entry", "that name is already taken", "the directory refused the change ...", "directory
             error: ..."; RuntimeError "directory operation failed: ..."; subprocess.TimeoutExpired) when it reads.
    Feeds:   device_overview; the web UI's dev preview (src/webui/devpreview).
    """
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
