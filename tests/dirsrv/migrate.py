"""Upgrade from before the directory split (fabriclib/ldap/migrate_local_suffix.py) against the test
389-DS container (dstest): an old-layout device in a role and an old service account are built as
Directory Manager, then migrated twice (the second run must change nothing).
Run by tests/dirsrv/run.sh after devices.py."""
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO, BASE = os.environ["REPO"], os.environ["BASE"]
LOCAL = f"ou=pi-core,{BASE}"
W = tempfile.mkdtemp(prefix="fabric-migrate-")
subprocess.run(["bash", f"{REPO}/installers/deb/assemble-tree.sh", W], check=True)   # the installed tree
sys.path.insert(0, f"{W}/fabric/lib")
from fabriclib.ldap.migrate_local_suffix import migrate_local_suffix  # noqa: E402

V = {"ldap_base_dn": BASE, "ldap_local_dn": LOCAL}
FAILED = 0

# Runs in dstest as Directory Manager; F_BASE/F_LOCAL arrive in the environment.
_DM = r'''
import json, os, sys, ldap
e = os.environ
BASE, LOCAL = e["F_BASE"], e["F_LOCAL"]
c = ldap.initialize("ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket")
c.simple_bind_s("cn=Directory Manager", e["DS_DM_PASSWORD"])
def add(dn, attrs):
    try:
        c.add_s(dn, [(k, [x.encode() for x in v]) for k, v in attrs.items()])
    except ldap.ALREADY_EXISTS:
        pass
def ls(dn, f="(objectClass=*)", at=None):
    try:
        return [(d, {k: [x.decode() for x in v] for k, v in a.items()}) for d, a in c.search_s(dn, ldap.SCOPE_ONELEVEL, f, at)]
    except ldap.NO_SUCH_OBJECT:
        return None
if sys.argv[1] == "build":
    add("ou=devices," + BASE, {"objectClass": ["top", "organizationalUnit"], "ou": ["devices"]})
    add("ou=admins,ou=accounts," + BASE, {"objectClass": ["top", "organizationalUnit"], "ou": ["admins"]})
    add("cn=old_admin,ou=admins,ou=accounts," + BASE, {"objectClass": ["top", "person"], "cn": ["old_admin"], "sn": ["old"]})
    for r in ("legacy-a", "legacy-b"):
        add("cn=%s,ou=device-roles,%s" % (r, BASE), {"objectClass": ["top", "groupOfNames", "fabricRole"], "cn": [r],
                                                     "fabricPriority": ["50"]})
    for n, mac, roles in (("old-pc", "02:00:00:00:10:01", ["legacy-a", "legacy-b"]), ("old-cam", "02:00:00:00:10:02", [])):
        dn = "cn=%s,ou=devices,%s" % (n, BASE)
        add(dn, {"objectClass": ["top", "device", "ieee802Device", "fabricDevice"], "cn": [n],
                 "fabricDeviceType": ["workstation"], "fabricEnabled": ["TRUE"], "macAddress": [mac]})
        for r in roles:
            c.modify_s("cn=%s,ou=device-roles,%s" % (r, BASE), [(ldap.MOD_ADD, "member", [dn.encode()])])
print(json.dumps({"new": ls("ou=devices," + LOCAL, "(cn=old-*)", ["fabricRoleName", "macAddress", "objectClass"]),
                  "old_devices": ls("ou=devices," + BASE),
                  "members": ls("ou=device-roles," + BASE, "(member=*)", ["cn"]),
                  "old_admins": ls("ou=admins,ou=accounts," + BASE),
                  "new_admins": [d for d, _ in ls("ou=admins," + LOCAL, at=["cn"]) or []]}))
'''


def dm(action):
    env = {**os.environ, "F_BASE": BASE, "F_LOCAL": LOCAL}
    res = subprocess.run(["docker", "exec", "-i", "-e", "F_BASE", "-e", "F_LOCAL", "dstest", "python3", "-", action],
                         input=_DM, env=env, capture_output=True, text=True, timeout=120)
    if res.returncode != 0:
        raise RuntimeError(res.stderr[-800:])
    return json.loads(res.stdout.strip().splitlines()[-1])


def check(name, cond, detail=""):
    global FAILED
    FAILED += not cond
    print(("PASS " if cond else "FAIL ") + name + ("" if cond else f"  -> {str(detail)[:400]}"))


try:
    before = dm("build")
    check("old layout built (2 devices, role members, old account)",
          len(before["old_devices"] or []) == 2 and before["members"] and before["old_admins"], before)
    first = migrate_local_suffix(V, container="dstest")
    check("first run moves 2 devices, 2 memberships, 1 old account",
          first == {"devices": 2, "role_members": 2, "accounts": 1}, first)
    after = dm("show")
    roles = {d.split(",")[0][3:]: sorted(a.get("fabricRoleName", [])) for d, a in after["new"] or []}
    check("devices are in the local suffix, naming their roles",
          roles == {"old-pc": ["legacy-a", "legacy-b"], "old-cam": []}, after["new"])
    check("moved devices keep their MAC and get fabricDeviceRoles",
          all("fabricDeviceRoles" in a["objectClass"] and a["macAddress"] for _, a in after["new"]), after["new"])
    check("old ou=devices and old service accounts are gone",
          after["old_devices"] is None and after["old_admins"] is None, after)
    check("no role lists members any more", after["members"] == [], after["members"])
    check("the seeded service accounts are untouched", len(after["new_admins"]) >= 6, after["new_admins"])
    second = migrate_local_suffix(V, container="dstest")
    check("second run changes nothing (idempotent)", second == {"devices": 0, "role_members": 0, "accounts": 0},
          second)
except Exception as e:  # noqa: BLE001 — report, don't crash the suite
    check("migration ran to the end", False, repr(e))
finally:
    shutil.rmtree(W, ignore_errors=True)
sys.exit(1 if FAILED else 0)
