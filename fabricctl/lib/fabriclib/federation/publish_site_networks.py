import json

from fabriclib.federation.common.run_in_directory import run_in_directory
from fabriclib.federation.site_networks import site_networks

# Reconciles ou=networks of this site's part with F_NETS: adds, changes and removes fabricNetwork entries.
_CODE = r'''
import ldap.dn
base, site, want = e["F_BASE"], e["F_SITE"], json.loads(e["F_NETS"])
def attrs(n):
    a = {"objectClass": [b"top", b"fabricNetwork"], "cn": [n["name"].encode()], "fabricCidr": [n["cidr"].encode()],
         "fabricSite": [site.encode()], "fabricNetworkKind": [n["kind"].encode()]}
    if n.get("vlan"):
        a["fabricVlan"] = [str(n["vlan"]).encode()]
    if n.get("notes"):
        a["description"] = [n["notes"].encode()]
    if n.get("allow_overlap"):
        a["fabricAllowOverlap"] = [n["allow_overlap"].encode()]
    return a
try:
    have = dict(c.search_s(base, ldap.SCOPE_ONELEVEL, "(objectClass=fabricNetwork)"))
except ldap.NO_SUCH_OBJECT:                       # an install seeded before the address plan existed
    c.add_s(base, ldap.modlist.addModlist({"objectClass": [b"top", b"organizationalUnit"], "ou": [b"networks"]}))
    have = {}
done = {"added": [], "changed": [], "removed": []}
keep = set()
for n in want:
    dn = "cn=%s,%s" % (ldap.dn.escape_dn_chars(n["name"]), base)
    keep.add(dn.lower())
    new = attrs(n)
    old = next((a for d, a in have.items() if d.lower() == dn.lower()), None)
    if old is None:
        c.add_s(dn, ldap.modlist.addModlist(new))
        done["added"].append(n["name"])
        continue
    mods = ldap.modlist.modifyModlist({k: v for k, v in old.items() if k != "objectClass"},
                                      {k: v for k, v in new.items() if k != "objectClass"})
    if mods:
        c.modify_s(dn, mods)
        done["changed"].append(n["name"])
for d in have:
    if d.lower() not in keep:
        c.delete_s(d)
        done["removed"].append(d)
print(json.dumps(done))
'''


def publish_site_networks(v, container="dirsrv"):
    """Purpose: write this site's networks (site_networks: the LAN and every DHCP subnet, with name, VLAN, notes)
             into ou=networks of its own part of the directory, so M5 replication carries them to the parent and
             the root, which gathers the address plan (manual 2.2.2.6).
    Inputs:  v — fabric vars: site_name, ldap_local_dn (ou=<site>,<base>), lan_cidr, install_kea, dhcp;
             container — the dirsrv container (tests pass theirs).
    Returns: {"added": [names], "changed": [names], "removed": [DNs]} — nothing when the directory already says
             the same.
    Fails:   ValidationError when 389-DS is not running; RuntimeError for other directory errors.
    Feeds:   ldap/run_directory_command (`fabricctl directory sync` and its 5-minute timer, federated installs)."""
    return run_in_directory(_CODE, {"BASE": f"ou=networks,{v['ldap_local_dn']}", "SITE": v["site_name"],
                                    "NETS": json.dumps(site_networks(v))}, container)
