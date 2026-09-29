import ipaddress

from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.common.save_vars import save_vars
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit
from fabriclib.dhcp.normalize_dhcp import normalize_dhcp


def add_reservation(actor, mac, ip, hostname="", source="cli"):
    """Reserve `ip` for `mac` (optionally with a hostname) in the DHCP subnet
    that contains it, in vars.yaml; the whole `dhcp:` block is validated
    again (inside the subnet, outside its pools, unique, no clash with a
    static record). Applied by the next apply. Returns the reservation."""
    try:
        addr = ipaddress.ip_address(str(ip).strip())
    except ValueError:
        raise ValidationError(f"{ip!r} is not an IPv4 address")
    with vars_lock():
        data = load_vars()
        dhcp = data.get("dhcp") or {}
        subnet = next((s for s in dhcp.get("subnets") or []
                       if addr in ipaddress.ip_network(str(s.get("subnet")), strict=False)), None)
        if subnet is None:
            raise ValidationError(f"{addr} is in none of the DHCP subnets")
        entry = {"mac": str(mac).strip(), "ip": str(addr), **({"hostname": hostname.strip()} if hostname else {})}
        subnet.setdefault("reservations", []).append(entry)
        dhcp = normalize_dhcp({**data, "dhcp": dhcp, "install_kea": True})
        data["dhcp"] = dhcp
        save_vars(data)
    saved = next(r for s in dhcp["subnets"] for r in s["reservations"] if r["ip"] == str(addr))
    write_audit(actor, "DHCP_RESERVE", f"{saved}", source)
    return saved
