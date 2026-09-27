import os
import subprocess

from fabriclib.common.errors import ValidationError

# Runs inside the dirsrv container (python3-ldap), bound as Directory Manager
# over LDAPI with the container's own DS_DM_PASSWORD. Inputs arrive as
# environment variables so no value appears in any argv.
_IN_CONTAINER = r'''
import os, time, ldap, ldap.modlist
e = os.environ
for _ in range(40):
    try:
        c = ldap.initialize("ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket")
        c.simple_bind_s("cn=Directory Manager", e["DS_DM_PASSWORD"])
        break
    except (ldap.INVALID_CREDENTIALS, ldap.SERVER_DOWN):
        time.sleep(3)
dn, group = e["F_DN"], e["F_GROUP"]
try:
    c.search_s(dn, ldap.SCOPE_BASE, "(objectClass=*)", ["uid"])
    state = "exists"
except ldap.NO_SUCH_OBJECT:
    u = e["F_UID"].encode()
    c.add_s(dn, ldap.modlist.addModlist({
        "objectClass": [b"top", b"person", b"organizationalPerson", b"inetOrgPerson"],
        "uid": [u], "cn": [u], "sn": [u], "givenName": [u],
        "mail": [e["F_MAIL"].encode()], "userPassword": [e["F_PW"].encode()]}))
    state = "created"
members = c.search_s(group, ldap.SCOPE_BASE, "(objectClass=*)", ["member"])[0][1].get("member", [])
if dn.lower() not in (m.decode().lower() for m in members):
    c.modify_s(group, [(ldap.MOD_ADD, "member", [dn.encode()])])
    state += "+member"
print(state)
'''


def ensure_admin_user(v, user, password, email, container="dirsrv"):
    """Make sure `user` exists in 389-DS (ou=users,ou=accounts) and is a member
    of the web UI admin group (Keycloak maps that group to fabric-admin).
    An existing entry is never changed (its password stays); membership is
    added if missing. Returns "created", "exists", with "+member" when the
    membership was added."""
    base = v["ldap_base_dn"]
    env = {**os.environ,
           "F_DN": f"uid={user},ou=users,ou=accounts,{base}",
           "F_GROUP": f"cn={v.get('webui_admin_group', 'admins')},ou=groups,{base}",
           "F_UID": user, "F_MAIL": email, "F_PW": password}
    res = subprocess.run(["docker", "exec", "-i", "-e", "F_DN", "-e", "F_GROUP", "-e", "F_UID", "-e", "F_MAIL",
                          "-e", "F_PW", container, "python3", "-"],
                         input=_IN_CONTAINER, env=env, capture_output=True, text=True, timeout=180)
    if res.returncode != 0:
        raise ValidationError(f"creating LDAP user {user} failed: {res.stderr.strip()[-500:]}")
    return res.stdout.strip().splitlines()[-1]
