from fabriclib.federation.common.run_in_directory import run_in_directory

# Gathers every site's ou=networks entries (the root holds a copy of each site's part) into ou=address-plan of
# the organisation, which replication copies to every site.
_CODE = r'''
import ldap.dn
base = e["F_BASE"]
plan = "ou=address-plan," + base
found = {}
for dn, a in c.search_s(base, ldap.SCOPE_SUBTREE, "(objectClass=fabricNetwork)"):
    parts = ldap.dn.str2dn(dn)
    if len(parts) < 3 or parts[1][0][1].lower() != "networks":
        continue                                  # an entry of the plan itself, not of a site
    site = (a.get("fabricSite") or [parts[2][0][1].encode()])[0].decode()
    name = a["cn"][0].decode()
    entry = {k: v for k, v in a.items() if k in ("fabricCidr", "fabricVlan", "fabricNetworkKind",
                                                 "fabricAllowOverlap", "description")}
    entry.update({"objectClass": [b"top", b"fabricNetwork"], "cn": [f"{site} {name}".encode()],
                  "fabricSite": [site.encode()]})
    found["cn=%s,%s" % (ldap.dn.escape_dn_chars(f"{site} {name}"), plan)] = entry
try:
    have = {d.lower(): (d, a) for d, a in c.search_s(plan, ldap.SCOPE_ONELEVEL, "(objectClass=fabricNetwork)")}
except ldap.NO_SUCH_OBJECT:                       # a root seeded before the address plan existed
    c.add_s(plan, ldap.modlist.addModlist({"objectClass": [b"top", b"organizationalUnit"], "ou": [b"address-plan"]}))
    have = {}
done = {"sites": sorted({a["fabricSite"][0].decode() for a in found.values()}), "added": 0, "changed": 0,
        "removed": 0}
for dn, new in found.items():
    old = have.pop(dn.lower(), None)
    if old is None:
        c.add_s(dn, ldap.modlist.addModlist(new))
        done["added"] += 1
        continue
    mods = ldap.modlist.modifyModlist({k: v for k, v in old[1].items() if k != "objectClass"},
                                      {k: v for k, v in new.items() if k != "objectClass"})
    if mods:
        c.modify_s(old[0], mods)
        done["changed"] += 1
for d, _ in have.values():
    c.delete_s(d)
    done["removed"] += 1
print(json.dumps(done))
'''


def publish_address_plan(v, container="dirsrv"):
    """Purpose: on the root site: gather every site's networks — its own and the copies of the sites' parts it
             holds — into ou=address-plan of the organisation, which replication copies read-only to every site,
             so each site can check new networks against all others even while the root is away (manual 2.2.2.6).
    Inputs:  v — fabric vars: ldap_base_dn; container — the dirsrv container (tests pass theirs).
    Returns: {"sites": [names in the plan], "added", "changed", "removed": counts}.
    Fails:   ValidationError when 389-DS is not running; RuntimeError for other directory errors.
    Feeds:   ldap/run_directory_command (`fabricctl directory sync` and its timer, on the root site only)."""
    return run_in_directory(_CODE, {"BASE": v["ldap_base_dn"]}, container)
