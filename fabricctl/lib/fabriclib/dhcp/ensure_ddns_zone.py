import os
import time


def ensure_ddns_zone(v, uid, gid):
    """Purpose: Create the DHCP subzone's file (SOA + NS) once. After that only Kea's DDNS writes to the zone, through
             BIND's journal.
    Inputs:  v — the vars dict (deploy_base_dir, domain, dhcp.ddns_subdomain default "dhcp").
             uid, gid — int owner of the file (BIND's user).
    Returns: True if the file was created, False if it already existed.
    Fails:   KeyError on missing vars; OSError if <deploy_base>/bind9/data is missing or not writable.
    Feeds:   deploy_kea.
    Notes:   fabric never rewrites this file, so hosts registered by DDNS survive every apply (design D16).
    """
    d = v.get("dhcp") or {}
    zone = f"{d.get('ddns_subdomain', 'dhcp')}.{v['domain']}"
    path = os.path.join(v["deploy_base_dir"], "bind9", "data", f"db.{zone}")
    if os.path.exists(path):
        return False
    serial = int(time.time()) + 1000000000
    text = (f"$TTL 3600\n$ORIGIN {zone}.\n"
            f"@  IN SOA ns.{v['domain']}. hostmaster.{v['domain']}. ({serial} 3600 1800 604800 300)\n"
            f"@  IN NS  ns.{v['domain']}.\n")
    with open(path, "w") as f:
        f.write(text)
    os.chown(path, uid, gid)
    os.chmod(path, 0o640)
    return True
