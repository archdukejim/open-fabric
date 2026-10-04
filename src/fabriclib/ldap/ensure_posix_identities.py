import json
import os
import re
import subprocess

from fabriclib.common.errors import ValidationError

UID_RE = re.compile(r"^[a-z_][a-z0-9_.-]{0,31}$")      # a safe login name and home folder (no /, no ..)

# Runs inside the dirsrv container, bound as Directory Manager over LDAPI with the container's own
# DS_DM_PASSWORD; inputs arrive as environment variables, nothing is on argv.
_IN_CONTAINER = r'''
import json, os, re, time, ldap
e = os.environ
for _ in range(40):
    try:
        c = ldap.initialize("ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket")
        c.simple_bind_s("cn=Directory Manager", e["DS_DM_PASSWORD"])
        break
    except (ldap.INVALID_CREDENTIALS, ldap.SERVER_DOWN):
        time.sleep(3)
safe = re.compile(e["F_UID_RE"])
done = {"added": [], "skipped": []}
people = c.search_s(e["F_USERS"], ldap.SCOPE_ONELEVEL,
                    "(&(objectClass=inetOrgPerson)(!(objectClass=posixAccount)))", ["uid"])
for dn, a in people:
    uid = (a.get("uid") or [b""])[0].decode()
    if not safe.match(uid):
        done["skipped"].append(uid or dn)
        continue
    # uidNumber -1: the DNA plugin replaces it with the next free number, server-side and atomically
    c.modify_s(dn, [(ldap.MOD_ADD, "objectClass", [b"posixAccount"]),
                    (ldap.MOD_ADD, "uidNumber", [b"-1"]),
                    (ldap.MOD_ADD, "gidNumber", [e["F_GID"].encode()]),
                    (ldap.MOD_ADD, "homeDirectory", [f"{e['F_HOME']}/{uid}".encode()]),
                    (ldap.MOD_ADD, "loginShell", [e["F_SHELL"].encode()])])
    number = c.search_s(dn, ldap.SCOPE_BASE, "(objectClass=*)", ["uidNumber"])[0][1]["uidNumber"][0].decode()
    if number == "-1":
        raise SystemExit("the DNA plugin did not assign a uidNumber (is it enabled? setup restarts 389-DS once)")
    done["added"].append(f"{uid}={number}")
print(json.dumps(done))
'''


def ensure_posix_identities(v, container="dirsrv"):
    """Purpose: give every person in the directory a POSIX identity (manual 2.10.1 step 1): posixAccount
             with a uidNumber the server assigns (389-DS DNA plugin, the users OU's uid_range, never handed out
             twice), the `users` group as primary group, /home/<uid> and a login shell.
    Inputs:  v — fabric vars: ldap_base_dn, ldap_groups (the `users` group's gidNumber, default 5000), optional
             posix_home_base (default /home) and posix_login_shell (default /bin/bash); container — the dirsrv
             container (tests pass theirs).
    Returns: {"added": ["<uid>=<uidNumber>", …], "skipped": [uids that are not safe login names]}; people who already
             have a POSIX identity are left as they are.
    Fails:   ValidationError when 389-DS is not running or the DNA plugin did not assign a number; RuntimeError for
             other failures (the container's message); subprocess.TimeoutExpired after 120 s.
    Feeds:   setup (start step after seeding, admin step), keycloak/create_person, `fabricctl directory sync`
             and its timer (people created in Keycloak's own console); tests/dirsrv/posix.py.
    Notes:   only where people are written (a standalone install, the root site); at a federated site people are a
             read-only copy and arrive with their identity (M5). A uid that is not a safe login name is never given
             a home folder path."""
    gid = next((int(g["gidNumber"]) for g in v.get("ldap_groups") or [] if g.get("name") == "users"), 5000)
    env = {**os.environ, "F_USERS": f"ou=users,ou=accounts,{v['ldap_base_dn']}", "F_GID": str(gid),
           "F_HOME": v.get("posix_home_base") or "/home", "F_SHELL": v.get("posix_login_shell") or "/bin/bash",
           "F_UID_RE": UID_RE.pattern}
    res = subprocess.run(["docker", "exec", "-i", "-e", "F_USERS", "-e", "F_GID", "-e", "F_HOME", "-e", "F_SHELL",
                          "-e", "F_UID_RE", container, "python3", "-"],
                         input=_IN_CONTAINER, env=env, capture_output=True, text=True, timeout=120)
    if res.returncode != 0 and ("No such container" in res.stderr or "is not running" in res.stderr):
        raise ValidationError("389-DS (dirsrv) is not running — `sudo fabricctl status`")
    if res.returncode != 0 and "DNA plugin" in (res.stderr + res.stdout):
        raise ValidationError((res.stderr + res.stdout).strip().splitlines()[-1])
    if res.returncode != 0 or not res.stdout.strip():
        raise RuntimeError(f"POSIX identities failed: {(res.stderr or res.stdout).strip()[-500:]}")
    return json.loads(res.stdout.strip().splitlines()[-1])
