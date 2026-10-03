"""POSIX identities (fabriclib/ldap/ensure_posix_identities.py, manual 2.10.1 step 1) against the test
389-DS container: the DNA plugin assigns uidNumbers server-side from the users OU's range, every person gets one
once, unsafe names are skipped, numbers are never handed out twice. Inputs from the environment."""
import os
import subprocess
import sys

sys.path[0:0] = [os.path.join(os.environ["REPO"], "fabricctl", "lib"), os.environ["REPO"]]
from fabriclib.ldap.ensure_posix_identities import ensure_posix_identities  # noqa: E402

BASE = os.environ["BASE"]
USERS = f"ou=users,ou=accounts,{BASE}"
V = {"ldap_base_dn": BASE, "ldap_groups": [{"name": "users", "gidNumber": 5000}]}
FAILED = 0


def check(name, cond, detail=""):
    global FAILED
    FAILED += not cond
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {detail}"))


def dm(code):
    """Run python-ldap code in the test container as Directory Manager; returns its output."""
    script = ("import ldap, os\nc = ldap.initialize('ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket')\n"
              "c.simple_bind_s('cn=Directory Manager', os.environ['DS_DM_PASSWORD'])\n" + code)
    return subprocess.run(["docker", "exec", "-i", "dstest", "python3", "-"], input=script, capture_output=True,
                          text=True).stdout


def add_person(uid):
    dm(f"import ldap.modlist\nc.add_s('uid={uid},{USERS}', ldap.modlist.addModlist({{'objectClass': [b'top', "
       f"b'person', b'organizationalPerson', b'inetOrgPerson'], 'uid': [b'{uid}'], 'cn': [b'{uid}'], "
       f"'sn': [b'{uid}']}}))")


def posix(uid):
    out = dm(f"a = c.search_s('uid={uid},{USERS}', ldap.SCOPE_BASE, attrlist=['uidNumber', 'gidNumber', "
             f"'homeDirectory', 'loginShell'])[0][1]\nprint({{k: v[0].decode() for k, v in a.items()}})")
    return eval(out.strip()) if out.strip() else {}


add_person("alice")
add_person("bob")
add_person("Bad.Name")                      # not a safe login name: skipped, never given /home/<it>
first = ensure_posix_identities(V, container="dstest")
numbers = {p.split("=")[0]: int(p.split("=")[1]) for p in first["added"]}
check("every person without one gets a POSIX identity (the admin user too)",
      {"jim", "alice", "bob"} <= set(numbers), first)
check("the server assigns the numbers from the users range, each once",
      all(5001 <= n <= 50000 for n in numbers.values()) and len(set(numbers.values())) == len(numbers), numbers)
a = posix("alice")
check("primary group users, /home/<uid>, /bin/bash",
      a.get("gidNumber") == "5000" and a.get("homeDirectory") == "/home/alice" and a.get("loginShell") == "/bin/bash", a)
check("an unsafe login name is skipped", first["skipped"] == ["Bad.Name"] and not posix("Bad.Name").get("uidNumber"),
      first)
again = ensure_posix_identities(V, container="dstest")
check("re-run changes nothing (identities kept)", again == {"added": [], "skipped": ["Bad.Name"]}
      and posix("alice").get("uidNumber") == str(numbers["alice"]), again)
dm(f"c.delete_s('uid=bob,{USERS}')")
add_person("carol")
third = ensure_posix_identities(V, container="dstest")
carol = int(third["added"][0].split("=")[1]) if third["added"] else 0
check("a deleted person's number is not handed out again", carol > max(numbers.values()), (third, numbers))
dm(f"c.delete_s('uid=Bad.Name,{USERS}')")
sys.exit(1 if FAILED else 0)
