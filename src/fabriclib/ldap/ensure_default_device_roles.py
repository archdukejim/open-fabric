import json
import os
import subprocess

from fabriclib.common.errors import ValidationError
from fabriclib.ldap.constants import DEFAULT_DEVICE_ROLES

# Runs inside the dirsrv container, bound as Directory Manager over LDAPI
# with the container's own DS_DM_PASSWORD; the roles arrive as JSON in the
# environment (nothing on argv).
_IN_CONTAINER = r'''
import json, os, time, ldap, ldap.modlist
e = os.environ
for _ in range(40):
    try:
        c = ldap.initialize("ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket")
        c.simple_bind_s("cn=Directory Manager", e["DS_DM_PASSWORD"])
        break
    except (ldap.INVALID_CREDENTIALS, ldap.SERVER_DOWN):
        time.sleep(3)
added = []
for name, perms, desc in json.loads(e["F_ROLES"]):
    try:
        c.add_s("cn=%s,ou=device-roles,%s" % (name, e["F_BASE"]), ldap.modlist.addModlist({
            "objectClass": [b"top", b"groupOfNames", b"fabricRole"], "cn": [name.encode()],
            "fabricPermission": [p.encode() for p in perms], "fabricPriority": [b"100"],
            "description": [desc.encode()]}))
        added.append(name)
    except ldap.ALREADY_EXISTS:
        pass
print(json.dumps(added))
'''


def ensure_default_device_roles(v, marker, container="dirsrv"):
    """Purpose: Create fabric's default device roles (DEFAULT_DEVICE_ROLES) once: on a new install, and on
             the first setup of an install from before they existed.
    Inputs:  v — fabric vars: ldap_base_dn; marker — path of the file recording that it was done;
             container — dirsrv container name, default "dirsrv".
    Returns: list of role names added ([] when the marker exists; roles that exist by name are left as
             they are).
    Fails:   ValidationError "creating the default device roles failed: <stderr tail>"; subprocess.
             TimeoutExpired after 180 s; OSError writing the marker.
    Feeds:   setup/start_services.py run.
    Notes:   binds as Directory Manager with the container's DS_DM_PASSWORD; roles arrive as JSON in the
             environment. The marker keeps a default role the admin deleted or renamed from coming back.
    """
    if os.path.exists(marker):
        return []
    env = {**os.environ, "F_BASE": v["ldap_base_dn"], "F_ROLES": json.dumps(DEFAULT_DEVICE_ROLES)}
    res = subprocess.run(["docker", "exec", "-i", "-e", "F_BASE", "-e", "F_ROLES", container, "python3", "-"],
                         input=_IN_CONTAINER, env=env, capture_output=True, text=True, timeout=180)
    if res.returncode != 0:
        raise ValidationError(f"creating the default device roles failed: {res.stderr.strip()[-500:]}")
    added = json.loads(res.stdout.strip().splitlines()[-1])
    with open(marker, "w") as f:
        f.write("default device roles created; delete this file to create the missing ones again\n")
    return added
