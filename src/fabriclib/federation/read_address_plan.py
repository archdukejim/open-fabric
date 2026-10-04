from fabriclib.federation.common.run_in_directory import run_in_directory

_CODE = r'''
out = []
try:
    rows = c.search_s("ou=address-plan," + e["F_BASE"], ldap.SCOPE_ONELEVEL, "(objectClass=fabricNetwork)")
except ldap.NO_SUCH_OBJECT:
    rows = []                                     # no plan yet: the root has not published one
for dn, a in rows:
    g = lambda k: (a.get(k) or [b""])[0].decode()
    out.append({"site": g("fabricSite"), "name": g("cn").split(" ", 1)[-1], "cidr": g("fabricCidr"),
                "vlan": int(g("fabricVlan")) if g("fabricVlan") else None, "kind": g("fabricNetworkKind"),
                "notes": g("description"), "allow_overlap": g("fabricAllowOverlap")})
print(json.dumps(sorted(out, key=lambda n: (n["site"], n["cidr"]))))
'''


def read_address_plan(v, container="dirsrv"):
    """Purpose: the address plan across sites, from this site's own copy of the organisation (manual 2.2.2.6): every
                site's networks with name, VLAN, kind and notes.
    Inputs:  v — fabric vars: ldap_base_dn; container — the dirsrv container (tests pass theirs).
    Returns: list of {"site", "name", "cidr", "vlan", "kind", "notes", "allow_overlap"}, sorted by site and
             network; [] before the root has published a plan.
    Fails:   ValidationError when 389-DS is not running; RuntimeError for other directory errors.
    Feeds:   federation/run_federation_command (`networks`), dhcp/common/edit_dhcp and accept_join (overlap
             checks)."""
    return run_in_directory(_CODE, {"BASE": v["ldap_base_dn"]}, container)
