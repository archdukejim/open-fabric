"""The address plan across sites without containers (design dhcp-management.md §5): what a site reports as its
networks, which overlaps are conflicts, what a joining site with an overlapping network is told, and the local
checks a DHCP subnet gets (fabric's own container network, the overlap reason). The directory side runs with two
real 389-DS in replication.sh."""
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(REPO, "fabricctl", "lib"))
from fabriclib.common.errors import ValidationError  # noqa: E402
from fabriclib.dhcp.normalize_dhcp import normalize_dhcp  # noqa: E402
from fabriclib.federation import accept_join as aj  # noqa: E402
from fabriclib.federation.network_conflicts import network_conflicts  # noqa: E402
from fabriclib.federation.site_networks import site_networks  # noqa: E402

FAILED = 0


def check(name, cond, detail=""):
    global FAILED
    FAILED += not cond
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {detail}"))


def refused(fn):
    try:
        fn()
    except ValidationError as e:
        return str(e)
    return ""


v = {"lan_cidr": "192.168.4.0/22", "install_kea": True,
     "dhcp": {"subnets": [{"subnet": "192.168.4.0/22", "name": "main"},
                          {"subnet": "192.168.20.0/24", "name": "iot", "vlan": 20, "notes": "cameras"},
                          {"subnet": "10.9.0.0/24"}]}}
nets = site_networks(v)
check("a site reports its LAN and every DHCP subnet once (the LAN that is a DHCP subnet keeps the subnet's name)",
      [(n["name"], n["cidr"], n["kind"]) for n in nets] == [("main", "192.168.4.0/22", "dhcp"),
                                                             ("iot", "192.168.20.0/24", "dhcp"),
                                                             ("10.9.0.0/24", "10.9.0.0/24", "dhcp")], nets)
check("without DHCP only the LAN", [n["name"] for n in site_networks({"lan_cidr": "10.1.0.0/24"})] == ["lan"])
plan = [{"site": "lan", "name": "main", "cidr": "192.168.0.0/22"},
        {"site": "lab", "name": "iot", "cidr": "192.168.20.0/24"},
        {"site": "barn", "name": "lan", "cidr": "192.168.20.128/25", "allow_overlap": "barn is never routed to lab"}]
c = network_conflicts([{"name": "iot", "cidr": "192.168.20.0/24"}], plan, "lab")
check("an overlap with another site is a conflict; this site's own entry is not; a reason on either side allows it",
      [(x["other_site"], bool(x["allowed"])) for x in c] == [("barn", True)], c)
c = network_conflicts([{"name": "x", "cidr": "192.168.2.0/24"}], plan, "lab")
check("a network inside another site's is found", c and c[0]["other_site"] == "lan" and not c[0]["allowed"], c)

aj.read_address_plan = lambda v: plan      # the upstream's copy of the plan (the directory side: replication.sh)
upstream = {"site_name": "lan", "lan_cidr": "192.168.0.0/22"}
msg = refused(lambda: aj._check_networks(upstream, "barn2", [{"name": "lan", "cidr": "192.168.1.0/24"}]))
check("a joining site whose network overlaps another site's is refused, naming both", "192.168.1.0/24 overlaps "
      "192.168.0.0/22 of site lan" in msg, msg)
check("a joining site with free networks is accepted; an older fabric that sends none too",
      refused(lambda: aj._check_networks(upstream, "barn2", [{"name": "lan", "cidr": "10.50.0.0/24"}])) == ""
      and refused(lambda: aj._check_networks(upstream, "barn2", [])) == "")
aj.read_address_plan = lambda v: (_ for _ in ()).throw(ValidationError("389-DS (dirsrv) is not running"))
check("with the directory away the upstream still checks against its own networks",
      "of site lan" in refused(lambda: aj._check_networks(upstream, "x", [{"name": "a", "cidr": "192.168.3.0/24"}])))
check("malformed networks in a join request are refused",
      "not valid" in refused(lambda: aj._check_networks(upstream, "x", [{"cidr": "not-a-net"}])))

base = {"install_kea": True, "dhcp": {"interfaces": ["eth0"]}}
msg = refused(lambda: normalize_dhcp({**base, "dhcp": {**base["dhcp"], "subnets": [
    {"subnet": "10.255.0.0/25", "pools": ["10.255.0.10 - 10.255.0.20"]}]}}))
check("a DHCP subnet overlapping fabric's own container network (fabric_subnet) is refused", "fabric_subnet" in msg, msg)
ok = normalize_dhcp({**base, "dhcp": {**base["dhcp"], "subnets": [
    {"subnet": "10.30.0.0/24", "pools": ["10.30.0.10 - 10.30.0.20"], "allow_overlap": "lab only"}]}})
check("allow_overlap is kept with the subnet", ok["subnets"][0]["allow_overlap"] == "lab only", ok)
print(f"\n{'FAILED' if FAILED else 'all passed'} ({FAILED} failures)")
sys.exit(1 if FAILED else 0)
