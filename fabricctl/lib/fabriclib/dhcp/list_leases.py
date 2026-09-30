import datetime

from fabriclib.dhcp.kea_command import kea_command


def list_leases(v):
    """Purpose: The DHCPv4 leases Kea holds (lease_cmds hook, lease4-get-all). Read-only.
    Inputs:  v — the vars dict (deploy_base_dir).
    Returns: [{"ip", "mac", "hostname", "subnet_id", "state" (active / declined / expired / ?), "expires" (local time,
             ISO to the minute; "" without cltt)}], latest expiry first.
    Fails:   ValidationError from kea_command; ValueError or TypeError on malformed lease fields.
    Feeds:   dhcp_overview; tests/kea/run.py.
    """
    out = []
    for lease in kea_command(v, "lease4-get-all").get("leases") or []:
        start = int(lease.get("cltt", 0))
        out.append({"ip": lease.get("ip-address"), "mac": lease.get("hw-address"),
                    "hostname": lease.get("hostname") or "", "subnet_id": lease.get("subnet-id"),
                    "state": {0: "active", 1: "declined", 2: "expired"}.get(lease.get("state", 0), "?"),
                    "expires": datetime.datetime.fromtimestamp(start + int(lease.get("valid-lft", 0)))
                    .isoformat(timespec="minutes") if start else ""})
    return sorted(out, key=lambda x: x["expires"], reverse=True)
