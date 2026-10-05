"""Run one directory operation for fabric-agent (manual 1.6.3, 2.11.2.16), inside the DC, signed in over LDAP as the
site's fabric-agent account — so AD's per-site limits apply to it (1.6.3.6) — never as the system.
    docker exec -i samba python3 /fabric/directory_op.py < request.json
The request on stdin (never a command line: it holds the account's password): {"op", "args" {…}, "site", "account",
"password"}. Prints one JSON object: {"result": …} or {"error": message, "kind": refused|exists|missing|invalid|other}
(exit 0 either way: the caller maps the kind to its own errors)."""
import json
import sys

import ldb
from samba.credentials import DONT_USE_KERBEROS, Credentials
from samba.param import LoadParm
from samba.samdb import SamDB

from directory_ops import OPS

CONF = "/data/etc/smb.conf"
# LDAP result codes -> what the caller is told
KINDS = {ldb.ERR_INSUFFICIENT_ACCESS_RIGHTS: "refused", ldb.ERR_ENTRY_ALREADY_EXISTS: "exists",
         ldb.ERR_NO_SUCH_OBJECT: "missing", ldb.ERR_CONSTRAINT_VIOLATION: "invalid",
         ldb.ERR_OBJECT_CLASS_VIOLATION: "invalid", ldb.ERR_UNWILLING_TO_PERFORM: "refused"}


def connect(site, account, password):
    """Purpose: the domain's database over LDAP on loopback, signed in as a site's account (NTLM: no Kerberos
             configuration needed inside the DC).
    Inputs:  site — str (for messages only); account — sAMAccountName; password — str.
    Returns: (SamDB, LoadParm).
    Fails:   ldb.LdbError when the sign-in is refused.
    Feeds:   run."""
    lp = LoadParm()
    lp.load(CONF)
    creds = Credentials()
    creds.guess(lp)
    creds.set_username(account)
    creds.set_password(password)
    creds.set_domain(lp.get("workgroup"))
    creds.set_kerberos_state(DONT_USE_KERBEROS)
    return SamDB(url="ldap://127.0.0.1", credentials=creds, lp=lp), lp


def run(request):
    """Purpose: one operation of directory_ops.OPS, as the request's account.
    Inputs:  request — dict: op (a key of OPS), args (dict), site, account, password.
    Returns: dict {"result": the operation's result} or {"error", "kind"}.
    Fails:   never: errors become {"error", "kind"} (an unknown op: kind "invalid").
    Feeds:   this script's main."""
    op = OPS.get(request.get("op"))
    if op is None:
        return {"error": f"unknown directory operation {request.get('op')!r}", "kind": "invalid"}
    try:
        samdb, lp = connect(request["site"], request["account"], request["password"])
        return {"result": op(samdb, lp, request["site"], **(request.get("args") or {}))}
    except ldb.LdbError as e:
        code, message = e.args[0], (e.args[1] if len(e.args) > 1 else str(e))
        return {"error": message, "kind": KINDS.get(code, "other")}
    except ValueError as e:
        return {"error": str(e), "kind": "invalid"}


if __name__ == "__main__":
    print(json.dumps(run(json.load(sys.stdin))))
