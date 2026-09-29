"""Device RBAC (fabriclib/ldap device and role operations) against the test
389-DS container (dstest), bound as cn=device_admin like fabric-agent.
Run by tests/dirsrv/run.sh after seeding and the admin-user test."""
import os
import shutil
import sys
import tempfile

REPO, BASE = os.environ["REPO"], os.environ["BASE"]
W = tempfile.mkdtemp(prefix="fabric-devices-")
shutil.copytree(os.path.join(REPO, "fabric", "lib"), f"{W}/fabric/lib")
os.makedirs(f"{W}/fabric/config")
with open(f"{W}/fabric/config/fabric-secrets.yml", "w") as f:
    f.write("ldap_device_admin_password: Da1\n")        # what tests/render.py seeded
sys.path.insert(0, f"{W}/fabric/lib")
from fabriclib.common.errors import ValidationError  # noqa: E402
from fabriclib.ldap.add_device import add_device  # noqa: E402
from fabriclib.ldap.add_role import add_role  # noqa: E402
from fabriclib.ldap.common.run_dirsrv import run_dirsrv  # noqa: E402
from fabriclib.ldap.link_device_cert import link_device_cert  # noqa: E402
from fabriclib.ldap.list_devices import list_devices  # noqa: E402
from fabriclib.ldap.list_people import list_people  # noqa: E402
from fabriclib.ldap.list_roles import list_roles  # noqa: E402
from fabriclib.ldap.remove_device import remove_device  # noqa: E402
from fabriclib.ldap.remove_role import remove_role  # noqa: E402
from fabriclib.ldap.update_device import update_device  # noqa: E402
from fabriclib.ldap.update_role import update_role  # noqa: E402

V = {"ldap_base_dn": BASE, "dirsrv_container": "dstest"}
FAILED = 0


def check(name, cond, detail=""):
    global FAILED
    FAILED += not cond
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {str(detail)[:400]}"))


def refused(fn, *args, match=""):
    try:
        fn(*args)
    except ValidationError as exc:
        return match.lower() in str(exc).lower() or str(exc)
    return False


def dev(name):
    return next((d for d in list_devices(V) if d["name"] == name), None)


# ---- roles
add_role(V, "alice", "trusted", {"permissions": ["network:eap-tls", "dns:dhcp-register", "pki:acme"],
                                 "vlan": "10", "priority": "10", "description": "Managed laptops"})
add_role(V, "alice", "iot", {"permissions": ["network:mab", "dns:dhcp-register"], "vlan": "30", "priority": "50"})
add_role(V, "alice", "guest", {})
roles = {r["name"]: r for r in list_roles(V)}
check("roles created (an empty role too), ordered by priority",
      [r["name"] for r in list_roles(V)] == ["trusted", "iot", "guest"] and roles["trusted"]["vlan"] == 10
      and roles["guest"]["permissions"] == [] and roles["guest"]["priority"] == 100, roles)
check("unknown permission refused", refused(add_role, V, "alice", "x", {"permissions": ["root:everything"]}, match="unknown"))
check("VLAN out of range refused", refused(add_role, V, "alice", "x", {"vlan": "5000"}, match="1 to 4094"))
check("bad role name refused", refused(add_role, V, "alice", "Bad Name", {}, match="role name"))
check("duplicate role refused", refused(add_role, V, "alice", "iot", {}, match="taken"))

# ---- devices
add_device(V, "alice", "laptop1", {"type": "laptop", "macs": ["AA-BB-CC-00-11-22"], "owner": "jim",
                                   "roles": ["trusted"], "description": "Jim's laptop"})
d = dev("laptop1")
check("device added: MAC normalised, owner, roles, effective permissions and VLAN",
      d and d["macs"] == ["aa:bb:cc:00:11:22"] and d["owner"] == "jim" and d["roles"] == ["trusted"]
      and d["permissions"] == ["dns:dhcp-register", "network:eap-tls", "pki:acme"] and d["vlan"] == 10, d)
add_device(V, "alice", "printer1", {"type": "printer", "macs": ["aabb.cc00.1133"], "roles": ["iot", "trusted"]})
p = dev("printer1")
check("several roles: permissions add up, VLAN from the lowest priority number",
      "network:mab" in p["permissions"] and "network:eap-tls" in p["permissions"] and p["vlan"] == 10
      and p["vlan_from"] == "trusted", p)
check("a MAC can belong to one device only",
      refused(add_device, V, "alice", "clone", {"macs": ["aa:bb:cc:00:11:22"]}, match="already belongs"))
check("multicast MAC refused", refused(add_device, V, "alice", "x1", {"macs": ["01:00:5e:00:00:01"]}, match="multicast"))
check("garbage MAC refused", refused(add_device, V, "alice", "x2", {"macs": ["nope"]}, match="not a MAC"))
check("bad device name refused", refused(add_device, V, "alice", "Bad_Name!", {}, match="device name"))
check("unknown role refused", refused(add_device, V, "alice", "x3", {"roles": ["admins"]}, match="no such role"))
check("unknown owner refused", refused(add_device, V, "alice", "x4", {"owner": "nobody"}, match="no such user"))
check("unknown type refused", refused(add_device, V, "alice", "x5", {"type": "toaster"}, match="type must be"))
check("duplicate device refused", refused(add_device, V, "alice", "laptop1", {}, match="already exists"))
check("refused adds left nothing behind", sorted(x["name"] for x in list_devices(V)) == ["laptop1", "printer1"])

update_device(V, "alice", "laptop1", {"type": "laptop", "macs": ["aa:bb:cc:00:11:22", "aa:bb:cc:00:11:23"],
                                      "owner": "jim", "roles": ["iot"], "enabled": False})
d = dev("laptop1")
check("update: roles swapped, second MAC, disabled -> no permissions, no VLAN",
      d["roles"] == ["iot"] and len(d["macs"]) == 2 and not d["enabled"] and d["permissions"] == []
      and d["vlan"] is None, d)
check("update: role membership really moved",
      "laptop1" not in {r["name"]: r for r in list_roles(V)}["trusted"]["members"])
update_role(V, "alice", "iot", {"permissions": ["network:mab"], "vlan": "", "priority": "50"})
check("role update: permissions and VLAN replaced",
      {r["name"]: r for r in list_roles(V)}["iot"]["vlan"] is None)

FP = ":".join(["AB"] * 32)
link_device_cert(V, "alice", "printer1", FP)
link_device_cert(V, "alice", "printer1", FP)
check("certificate fingerprint linked (idempotent)", dev("printer1")["certs"] == [FP], dev("printer1"))
link_device_cert(V, "alice", "printer1", FP, link=False)
check("certificate fingerprint unlinked", dev("printer1")["certs"] == [])
check("malformed fingerprint refused", refused(link_device_cert, V, "alice", "printer1", "abc", match="SHA-256"))

check("a role with devices cannot be removed", refused(remove_role, V, "alice", "iot", match="still has"))
remove_device(V, "alice", "laptop1")
remove_device(V, "alice", "printer1")
check("devices removed and taken out of their roles",
      list_devices(V) == [] and all(not r["members"] for r in list_roles(V)))
for r in ("trusted", "iot", "guest"):
    remove_role(V, "alice", r)
check("empty roles removed", list_roles(V) == [])

# ---- people (read-only) and least privilege
people = list_people(V)
jim = next((u for u in people["users"] if u["uid"] == "jim"), None)
check("people: users with their groups, no passwords", jim and "admins" in jim["groups"]
      and "userPassword" not in str(people), people)
check("device_admin cannot modify people",
      refused(run_dirsrv, V, 'c.modify_s(USERS.replace("ou=users", "uid=jim,ou=users"), '
                             '[(ldap.MOD_REPLACE, "mail", [b"x@evil"])])\nout({"ok": True})', match="not permitted"))
check("device_admin cannot change security groups",
      refused(run_dirsrv, V, 'c.modify_s("cn=admins," + GROUPS, [(ldap.MOD_ADD, "member", [b"cn=x"])])\n'
                             'out({"ok": True})', match="not permitted"))
check("device_admin cannot read passwords",
      "userPassword" not in str(run_dirsrv(V, 'out(str(c.search_s("cn=super_admin,ou=admins,ou=accounts," + BASE, '
                                             'ldap.SCOPE_BASE)))')))
audit = open(f"{W}/fabric/archive/audit.log").read()
check("every change audited", all(a in audit for a in ("ROLE_ADD", "DEVICE_ADD", "DEVICE_UPDATE", "DEVICE_CERT_LINK",
                                                       "DEVICE_REMOVE", "ROLE_REMOVE")))
shutil.rmtree(W)
sys.exit(1 if FAILED else 0)
