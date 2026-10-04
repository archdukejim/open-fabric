"""S0 spike Q11, step 1: fill a real 389-DS (seeded by fabric) the way fabric does — device roles and devices through
fabric's own functions (fabriclib.ldap, as fabric-agent calls them), people with POSIX ids and a site network in
fabric's entry shapes — then export the organisation and site parts as JSON for the migration.
    REPO=… BASE=… W=… python3 q11-populate.py   (needs the 389-DS container s0-ds)"""
import json
import os
import subprocess
import sys

REPO, BASE, W = os.environ["REPO"], os.environ["BASE"], os.environ["W"]
LOCAL = f"ou=pi-core,{BASE}"
tree = f"{W}/tree"
subprocess.run(["bash", f"{REPO}/packaging/deb/assemble-tree.sh", tree], check=True)
os.makedirs(f"{tree}/fabric/config", exist_ok=True)
with open(f"{tree}/fabric/config/fabric-secrets.yml", "w") as f:
    f.write("ldap_device_admin_password: Da1\n")         # what tests/render.py seeded
sys.path.insert(0, f"{tree}/fabric/lib")
from fabriclib.ldap.add_device import add_device  # noqa: E402
from fabriclib.ldap.add_role import add_role  # noqa: E402
from fabriclib.ldap.link_device_cert import link_device_cert  # noqa: E402

V = {"ldap_base_dn": BASE, "ldap_local_dn": LOCAL, "dirsrv_container": "s0-ds"}


def ds(script):
    """Run python-ldap code in the 389-DS container as Directory Manager over LDAPI; returns its stdout."""
    head = ("import ldap, json\nc = ldap.initialize('ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket')\n"
            "c.simple_bind_s('cn=Directory Manager', 'DmPass1')\n")
    return subprocess.run(["docker", "exec", "-i", "s0-ds", "python3", "-"], input=head + script, text=True,
                          capture_output=True, check=True).stdout


# device roles and devices, through fabric's own functions
add_role(V, "spike", "trusted", {"permissions": ["network:eap-tls", "dns:dhcp-register"], "vlan": "10",
                                 "priority": "10", "description": "Managed laptops"})
add_role(V, "spike", "iot", {"permissions": ["network:mab"], "vlan": "30", "priority": "50"})
add_device(V, "spike", "printer1", {"type": "printer", "macs": ["02:00:00:00:00:01"], "roles": ["iot"]})
add_device(V, "spike", "laptop1", {"type": "laptop", "macs": ["02:00:00:00:00:02", "02:00:00:00:00:03"],
                                   "roles": ["trusted", "iot"]})
link_device_cert(V, "spike", "laptop1", ":".join(["AB"] * 32))
# people with POSIX identities and a group membership, and a site network, in fabric's shapes
ds(f"""
for uid, n, given, sn in (("carol", 5001, "Carol", "Lee"), ("dave", 5002, "Dave", "Ray")):
    c.add_s(f"uid={{uid}},ou=users,ou=accounts,{BASE}", [
        ("objectClass", [b"top", b"person", b"organizationalPerson", b"inetOrgPerson", b"posixAccount"]),
        ("uid", [uid.encode()]), ("cn", [f"{{given}} {{sn}}".encode()]), ("givenName", [given.encode()]),
        ("sn", [sn.encode()]), ("mail", [f"{{uid}}@lan.test".encode()]), ("uidNumber", [str(n).encode()]),
        ("gidNumber", [b"5000"]), ("homeDirectory", [f"/home/{{uid}}".encode()]), ("loginShell", [b"/bin/bash"])])
c.modify_s("cn=admins,ou=groups,{BASE}", [(ldap.MOD_ADD, "member", [b"uid=carol,ou=users,ou=accounts,{BASE}"])])
c.add_s("cn=lan,ou=networks,{LOCAL}", [("objectClass", [b"top", b"fabricNetwork"]), ("cn", [b"lan"]),
        ("fabricCidr", [b"192.168.7.0/24"]), ("fabricSite", [b"pi-core"]), ("fabricVlan", [b"1"]),
        ("fabricNetworkKind", [b"lan"])])
""")
# export: every entry of both parts, its attributes as lists of strings
out = ds(f"""
res = []
for base in ("{BASE}",):
    for dn, attrs in c.search_s(base, ldap.SCOPE_SUBTREE, "(objectClass=*)"):
        res.append([dn, {{k: [v.decode("utf-8", "replace") for v in vs] for k, vs in attrs.items()
                          if k.lower() not in ("userpassword", "nsuniqueid")}}])
print(json.dumps(res))
""")
entries = json.loads(out)
with open(f"{W}/export.json", "w") as f:
    json.dump(entries, f, indent=1)
print(f"exported {len(entries)} entries from 389-DS")
