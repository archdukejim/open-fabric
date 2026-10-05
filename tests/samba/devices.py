"""The `samba` suite, devices and device roles (manual 1.6.3.4, S3): fabric's own device and role functions — exactly
what fabric-agent calls — against a real DC, as the site's agent account. The DC runs under the product's container
name, `samba`, on a private test network; fabric's secrets and audit log are stood in for.
    sudo python3 tests/samba/devices.py
"""
import os
import subprocess
import sys

REPO = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path[0:0] = [os.path.join(REPO, "src"), os.path.dirname(os.path.abspath(__file__))]
from start_dc import start_dc  # noqa: E402
import fabriclib.directory.add_device as m_add_device  # noqa: E402
import fabriclib.directory.add_role as m_add_role  # noqa: E402
import fabriclib.directory.common.read_directory as m_read  # noqa: E402
import fabriclib.directory.link_device_cert as m_link  # noqa: E402
import fabriclib.directory.remove_device as m_remove_device  # noqa: E402
import fabriclib.directory.remove_role as m_remove_role  # noqa: E402
import fabriclib.directory.update_device as m_update_device  # noqa: E402
import fabriclib.directory.update_role as m_update_role  # noqa: E402
from fabriclib.common.errors import ValidationError  # noqa: E402
from fabriclib.directory.ensure_default_device_roles import ensure_default_device_roles  # noqa: E402
from fabriclib.directory.list_devices import list_devices  # noqa: E402
from fabriclib.directory.list_roles import list_roles  # noqa: E402
from fabriclib.directory.run_op import run_op  # noqa: E402
from fabriclib.secrets.random_password import random_password  # noqa: E402

W = os.path.join(os.environ.get("FABRIC_TEST_OUT", "/tmp/fabric-tests"), "samba-devices")
NET, SUBNET, IP = "sambadev_net", "10.254.32.0/24", "10.254.32.10"
DC = "samba"            # the product's own name: fabric's functions use it
FAILED = 0
AUDIT = []


def check(name, cond, detail=""):
    global FAILED
    FAILED += not cond
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {str(detail)[:400]}"))


def refused(fn, *args, match=""):
    """True only if fn(*args) raises a ValidationError whose message contains `match`."""
    try:
        fn(*args)
    except ValidationError as exc:
        if match.lower() in str(exc).lower():
            return True
        print(f"    refused, but not for {match!r}: {exc}")
    return False


if subprocess.run(["docker", "inspect", "samba"], capture_output=True).returncode == 0 and \
        not subprocess.run(["docker", "inspect", "-f", "{{.Config.Image}}", "samba"], capture_output=True,
                           text=True).stdout.strip().endswith(":test"):
    sys.exit("a container named samba that is not a test DC runs here: not touching it")
dc = start_dc(W, DC, NET, SUBNET, IP)
V, SECRETS = dc["v"], dc["secrets"]
for mod in (m_add_device, m_add_role, m_read, m_link, m_remove_device, m_remove_role, m_update_device, m_update_role):
    if hasattr(mod, "load_secrets"):
        mod.load_secrets = lambda: SECRETS
    if hasattr(mod, "write_audit"):
        mod.write_audit = lambda actor, event, detail, source: AUDIT.append(event)
add_device, add_role = m_add_device.add_device, m_add_role.add_role
update_device, update_role = m_update_device.update_device, m_update_role.update_role
remove_device, remove_role, link_device_cert = m_remove_device.remove_device, m_remove_role.remove_role, \
    m_link.link_device_cert


def dev(name):
    return next((d for d in list_devices(V) if d["name"] == name), None)


# ---- fabric's default roles, once, in the organisation's OU=device-roles
marker = os.path.join(W, ".default-device-roles")
added = ensure_default_device_roles(V, SECRETS, marker)
check("fabric's six default device roles are made once, in the organisation's OU",
      len(added) == 6 and ensure_default_device_roles(V, SECRETS, marker) == []
      and all(",OU=device-roles,OU=organisation," in r["dn"] for r in m_read.read_directory(V)["roles"]),
      added)
for name in added:                       # the rest of the test starts from no roles, as the 389-DS suite did
    remove_role(V, "alice", name)

# ---- roles
add_role(V, "alice", "trusted", {"permissions": ["network:eap-tls", "dns:dhcp-register", "pki:acme"],
                                 "vlan": "10", "priority": "10", "description": "Managed laptops"})
add_role(V, "alice", "iot", {"permissions": ["network:mab", "dns:dhcp-register"], "vlan": "30", "priority": "50"})
add_role(V, "alice", "guest", {})
roles = {r["name"]: r for r in list_roles(V)}
check("roles created (an empty role too), ordered by priority, in the site's OU=device-roles",
      [r["name"] for r in list_roles(V)] == ["trusted", "iot", "guest"] and roles["trusted"]["vlan"] == 10
      and roles["guest"]["permissions"] == [] and roles["guest"]["priority"] == 100
      and ",OU=device-roles,OU=lan,OU=sites," in m_read.read_directory(V)["roles"][0]["dn"], roles)
check("unknown permission refused", refused(add_role, V, "alice", "x", {"permissions": ["root:everything"]},
                                            match="unknown"))
check("VLAN out of range refused", refused(add_role, V, "alice", "x", {"vlan": "5000"}, match="1 to 4094"))
check("bad role name refused", refused(add_role, V, "alice", "Bad Name", {}, match="role name"))
check("duplicate role refused", refused(add_role, V, "alice", "iot", {}, match="taken"))

# ---- devices (their owner a person of the site)
run_op(V, SECRETS, "create_person", {"uid": "jim", "first": "Jim", "last": "J", "email": "jim@lan.test",
                                     "password": "Pw-" + random_password(20), "gid": 5000, "home_base": "/home",
                                     "shell": "/bin/bash"}, DC)
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
check("multicast MAC refused", refused(add_device, V, "alice", "x1", {"macs": ["01:00:5e:00:00:01"]},
                                       match="multicast"))
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
check("role update: permissions and VLAN replaced", {r["name"]: r for r in list_roles(V)}["iot"]["vlan"] is None)

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
check("every change audited", all(a in AUDIT for a in ("ROLE_ADD", "DEVICE_ADD", "DEVICE_UPDATE", "DEVICE_CERT_LINK",
                                                       "DEVICE_REMOVE", "ROLE_REMOVE")), AUDIT)

subprocess.run(["docker", "rm", "-f", DC], capture_output=True)
subprocess.run(["docker", "network", "rm", NET], capture_output=True)
sys.exit(1 if FAILED else 0)
