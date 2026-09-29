import ipaddress
import re

from fabriclib.common.errors import ValidationError

IFACE_RE = re.compile(r"^[A-Za-z0-9._-]{1,15}$")
LABEL_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?$")
MAC_RE = re.compile(r"^[0-9a-f]{2}(:[0-9a-f]{2}){5}$")


def _pool(text, net):
    try:
        lo, hi = (ipaddress.ip_address(p.strip()) for p in str(text).split("-"))
    except ValueError:
        raise ValidationError(f"pool {text!r}: 'first - last' addresses")
    if not (lo in net and hi in net and lo <= hi):
        raise ValidationError(f"pool {text}: must lie inside {net}, first <= last")
    return lo, hi


def normalize_dhcp(v):
    """Check `dhcp:` (and that nothing static collides with it) before
    anything is rendered: interfaces, subnets, pools inside their subnet,
    routers, reservations (MAC, address inside the subnet but outside its
    pools, unique), the DDNS subdomain, the lease time; and no static A
    record of the zones inside a pool (Kea would hand that address out).
    Returns the normalised dict; raises ValidationError."""
    d = dict(v.get("dhcp") or {})
    if not v.get("install_kea"):
        return d
    ifaces = d.get("interfaces") or []
    if not ifaces or not all(isinstance(i, str) and IFACE_RE.match(i) for i in ifaces):
        raise ValidationError("dhcp.interfaces: the host interface(s) to serve, e.g. [eth0]")
    if not LABEL_RE.match(str(d.get("ddns_subdomain", "dhcp"))):
        raise ValidationError("dhcp.ddns_subdomain: one DNS label, e.g. dhcp")
    lease = d.get("lease_time", 86400)
    if not isinstance(lease, int) or not 300 <= lease <= 2592000:
        raise ValidationError("dhcp.lease_time: seconds, 300 to 2592000")
    subnets, pools_all, seen_ips, seen_macs = [], [], set(), set()
    for s in d.get("subnets") or []:
        try:
            net = ipaddress.ip_network(str(s.get("subnet")), strict=True)
        except ValueError:
            raise ValidationError(f"dhcp subnet {s.get('subnet')!r}: a network like 192.168.4.0/22")
        if net.version != 4:
            raise ValidationError(f"{net}: DHCPv4 subnets only")
        pools = [_pool(p, net) for p in s.get("pools") or []]
        if s.get("routers") and ipaddress.ip_address(str(s["routers"])) not in net:
            raise ValidationError(f"{net}: router {s['routers']} is outside the subnet")
        reservations = []
        for r in s.get("reservations") or []:
            mac = str(r.get("mac", "")).lower().replace("-", ":")
            if not MAC_RE.match(mac):
                raise ValidationError(f"reservation {r}: MAC like aa:bb:cc:dd:ee:ff")
            try:
                ip = ipaddress.ip_address(str(r.get("ip", "")))
            except ValueError:
                raise ValidationError(f"reservation {mac}: address {r.get('ip')!r} is not an IPv4 address")
            if ip not in net or any(lo <= ip <= hi for lo, hi in pools):
                raise ValidationError(f"reservation {ip}: inside {net} but outside its pools")
            if ip in seen_ips or mac in seen_macs:
                raise ValidationError(f"reservation {mac} / {ip}: MAC and address must be unique")
            seen_ips.add(ip)
            seen_macs.add(mac)
            host = r.get("hostname") or ""
            if host and not LABEL_RE.match(host):
                raise ValidationError(f"reservation hostname {host!r}: one DNS label")
            reservations.append({"mac": mac, "ip": str(ip), **({"hostname": host} if host else {})})
        pools_all += pools
        subnets.append({**s, "subnet": str(net), "reservations": reservations})
    if not subnets:
        raise ValidationError("dhcp.subnets: at least one subnet with a pool")
    for zone in (v.get("dns") or {}).values():
        for rec in (zone or {}).get("A") or []:
            try:
                ip = ipaddress.ip_address(str(rec.get("ip")))
            except ValueError:
                continue
            if any(lo <= ip <= hi for lo, hi in pools_all):
                raise ValidationError(f"DNS record {rec.get('name')} = {ip} is inside a DHCP pool: make it a "
                                      "DHCP reservation, or move the pool")
    return {**d, "subnets": subnets}
