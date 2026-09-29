import datetime

from fabriclib.dhcp.kea_command import kea_command


def list_leases(v):
    """Active DHCPv4 leases from Kea (lease_cmds hook): [{ip, mac,
    hostname, expires, subnet_id, state}], latest expiry first. Read-only."""
    out = []
    for lease in kea_command(v, "lease4-get-all").get("leases") or []:
        start = int(lease.get("cltt", 0))
        out.append({"ip": lease.get("ip-address"), "mac": lease.get("hw-address"),
                    "hostname": lease.get("hostname") or "", "subnet_id": lease.get("subnet-id"),
                    "state": {0: "active", 1: "declined", 2: "expired"}.get(lease.get("state", 0), "?"),
                    "expires": datetime.datetime.fromtimestamp(start + int(lease.get("valid-lft", 0)))
                    .isoformat(timespec="minutes") if start else ""})
    return sorted(out, key=lambda x: x["expires"], reverse=True)
