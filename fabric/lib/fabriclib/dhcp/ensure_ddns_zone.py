import os
import time


def ensure_ddns_zone(v, uid, gid):
    """Create the DHCP subzone's file once (SOA + NS). After that only Kea's
    DDNS writes to the zone, through BIND's journal: fabric never rewrites
    this file, so registered hosts survive every apply (design D16).
    Returns True if it was created."""
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
