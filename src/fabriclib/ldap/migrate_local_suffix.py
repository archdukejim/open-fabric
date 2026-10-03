import json
import os
import subprocess

from fabriclib.common.errors import ValidationError

# Runs inside the dirsrv container, bound as Directory Manager over LDAPI with
# the container's own DS_DM_PASSWORD; the suffixes arrive in the environment.
_IN_CONTAINER = r'''
import json, os, time, ldap, ldap.modlist
e = os.environ
BASE, LOCAL = e["F_BASE"], e["F_LOCAL"]
OLD_DEV, NEW_DEV = "ou=devices," + BASE, "ou=devices," + LOCAL
OLD_ADMINS, ROLES = "ou=admins,ou=accounts," + BASE, "ou=device-roles," + BASE
for _ in range(40):
    try:
        c = ldap.initialize("ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket")
        c.simple_bind_s("cn=Directory Manager", e["DS_DM_PASSWORD"])
        break
    except (ldap.INVALID_CREDENTIALS, ldap.SERVER_DOWN):
        time.sleep(3)
def children(dn):
    try:
        return c.search_s(dn, ldap.SCOPE_ONELEVEL, "(objectClass=*)")
    except ldap.NO_SUCH_OBJECT:
        return None
done = {"devices": 0, "role_members": 0, "accounts": 0}
roles = c.search_s(ROLES, ldap.SCOPE_ONELEVEL, "(objectClass=groupOfNames)", ["cn", "member"])
old_devices = children(OLD_DEV)
if old_devices is not None:
    for dn, a in old_devices:
        name = a["cn"][0].decode()
        member_of = sorted(r[1]["cn"][0].decode() for r in roles
                           if dn.lower() in {m.decode().lower() for m in r[1].get("member", [])})
        attrs = {k: v for k, v in a.items()}
        classes = [x for x in attrs.get("objectClass", []) if x.lower() != b"fabricdeviceroles"]
        attrs["objectClass"] = classes + [b"fabricDeviceRoles"]
        if member_of:
            attrs["fabricRoleName"] = [r.encode() for r in member_of]
        try:
            c.add_s("cn=%s,%s" % (name, NEW_DEV), ldap.modlist.addModlist(attrs))
            done["devices"] += 1
        except ldap.ALREADY_EXISTS:
            pass
    for dn, _ in old_devices:
        c.delete_s(dn)
    c.delete_s(OLD_DEV)
    done["role_members"] = sum(len(r[1].get("member", [])) for r in roles)
# A role lists no members any more: the devices name their roles. Re-read: deleting the old devices
# made referential integrity drop most member values already.
for dn, a in c.search_s(ROLES, ldap.SCOPE_ONELEVEL, "(&(objectClass=groupOfNames)(member=*))", ["member"]):
    try:
        c.modify_s(dn, [(ldap.MOD_DELETE, "member", None)])
    except ldap.NO_SUCH_ATTRIBUTE:
        pass
old_accounts = children(OLD_ADMINS)
if old_accounts is not None:
    for dn, _ in old_accounts:
        c.delete_s(dn)
        done["accounts"] += 1
    c.delete_s(OLD_ADMINS)
print(json.dumps(done))
'''


def migrate_local_suffix(v, container="dirsrv"):
    """Purpose: Move an install from before the directory split (manual 1.8, M1) to the split
             layout: its devices from ou=devices of the organisation suffix to ou=devices of its local suffix,
             each naming its roles (fabricRoleName, taken from the roles' old member lists); roles' member
             lists removed; the old service accounts (ou=admins,ou=accounts) and their OU deleted.
    Inputs:  v — fabric vars: ldap_base_dn, ldap_local_dn; container — dirsrv container name, default
             "dirsrv". The local suffix and its new service accounts must already exist (the seed made them).
    Returns: {"devices": moved, "role_members": role memberships carried over (counted from the member lists
             when old devices were found), "accounts": old accounts deleted} — all 0 on an install already
             migrated (idempotent; a run interrupted part-way finishes on the next).
    Fails:   ValidationError "moving the directory to the local suffix failed: <stderr tail>" (an LDAP error
             inside the container); subprocess.TimeoutExpired after 180 s.
    Feeds:   setup/start_services.py run (after Keycloak is bound to its new account).
    Notes:   binds as Directory Manager with the container's DS_DM_PASSWORD. Run after keycloak_bootstrap has
             moved Keycloak's LDAP bind to the new keycloak_admin: deleting the old accounts earlier would
             break sign-in until then. A device already present in the local suffix is not overwritten.
             Deleting an old device lets 389-DS referential integrity drop it from the roles, so member
             values are removed from a fresh read.
    """
    env = {**os.environ, "F_BASE": v["ldap_base_dn"], "F_LOCAL": v["ldap_local_dn"]}
    res = subprocess.run(["docker", "exec", "-i", "-e", "F_BASE", "-e", "F_LOCAL", container, "python3", "-"],
                         input=_IN_CONTAINER, env=env, capture_output=True, text=True, timeout=180)
    if res.returncode != 0:
        raise ValidationError(f"moving the directory to the local suffix failed: {res.stderr.strip()[-500:]}")
    return json.loads(res.stdout.strip().splitlines()[-1])
