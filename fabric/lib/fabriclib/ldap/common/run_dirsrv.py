import json
import os
import subprocess
import textwrap

import yaml

from fabriclib.common.errors import ValidationError
from fabriclib.common.paths import SECRETS_FILE

# Runs inside the dirsrv container (python3-ldap), bound over LDAPI as the
# least-privilege cn=device_admin — never Directory Manager — so the
# directory's ACIs, not this code, decide what can change. Inputs arrive as
# JSON in an environment variable; the password too. Nothing is on argv.
_PRELUDE = r'''
import json, os, time, ldap, ldap.modlist
e = os.environ
IN = json.loads(e["F_JSON"])
BASE = e["F_BASE"]
DEV, ROLES = "ou=devices," + BASE, "ou=device-roles," + BASE
USERS, GROUPS = "ou=users,ou=accounts," + BASE, "ou=groups," + BASE
class Refused(Exception):
    pass
def s(vals):
    return [v.decode() for v in vals or []]
def one(a, k, default=""):
    return s(a.get(k))[0] if a.get(k) else default
def out(obj):
    print("\n" + json.dumps(obj))
for _ in range(20):
    try:
        c = ldap.initialize("ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket")
        c.simple_bind_s("cn=device_admin,ou=admins,ou=accounts," + BASE, e["F_PW"])
        break
    except ldap.SERVER_DOWN:
        time.sleep(1)
'''
_EPILOGUE = r'''
except Refused as x:
    out({"error": str(x)})
except ldap.ALREADY_EXISTS:
    out({"error": "that name is already taken"})
except ldap.NO_SUCH_OBJECT:
    out({"error": "no such entry"})
except ldap.INSUFFICIENT_ACCESS:
    out({"error": "the directory refused the change (not permitted for cn=device_admin)"})
except ldap.LDAPError as x:
    out({"error": "directory error: " + str(x.args[0].get("desc", x) if x.args else x)})
'''


def run_dirsrv(v, snippet, payload=None):
    """Run a directory operation (python snippet using `c`, `IN`, `out`,
    `Refused`, `DEV`, `ROLES`, `USERS`, `GROUPS`) in the dirsrv container
    as cn=device_admin. Returns what the snippet passed to out(); a
    Refused(...) or LDAP refusal becomes a ValidationError."""
    try:
        with open(SECRETS_FILE) as f:
            password = (yaml.safe_load(f) or {}).get("ldap_device_admin_password")
    except FileNotFoundError:
        password = None
    if not password:
        raise ValidationError("ldap_device_admin_password is missing: re-run `sudo fabricctl setup`")
    script = _PRELUDE + "try:\n" + textwrap.indent(textwrap.dedent(snippet), "    ") + _EPILOGUE
    env = {**os.environ, "F_JSON": json.dumps(payload or {}), "F_BASE": v["ldap_base_dn"], "F_PW": password}
    res = subprocess.run(["docker", "exec", "-i", "-e", "F_JSON", "-e", "F_BASE", "-e", "F_PW",
                          v.get("dirsrv_container", "dirsrv"), "python3", "-"],
                         input=script, env=env, capture_output=True, text=True, timeout=60)
    if res.returncode != 0 and ("No such container" in res.stderr or "is not running" in res.stderr):
        raise ValidationError("389-DS (dirsrv) is not running — `sudo fabricctl status`")
    if res.returncode != 0 or not res.stdout.strip():
        raise RuntimeError(f"directory operation failed: {(res.stderr or res.stdout).strip()[-500:]}")
    result = json.loads(res.stdout.strip().splitlines()[-1])
    if isinstance(result, dict) and "error" in result and len(result) == 1:
        raise ValidationError(result["error"])
    return result
