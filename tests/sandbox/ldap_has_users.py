#!/usr/bin/env python3
"""Inside the sandbox: how many of the given uids exist in 389-DS
(bound as Directory Manager over LDAPI inside the dirsrv container).

    python3 ldap_has_users.py <base dn> <uid> [<uid> …]    prints a number
"""
import subprocess
import sys

base, uids = sys.argv[1], sys.argv[2:]
flt = "(|" + "".join(f"(uid={u})" for u in uids) + ")"
code = ("import os, ldap; c = ldap.initialize('ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket'); "
        "c.simple_bind_s('cn=Directory Manager', os.environ['DS_DM_PASSWORD']); "
        f"print(len(c.search_s('ou=users,ou=accounts,{base}', ldap.SCOPE_ONELEVEL, '{flt}', ['uid'])))")
res = subprocess.run(["docker", "exec", "dirsrv", "python3", "-c", code], capture_output=True, text=True)
print(res.stdout.strip() or res.stderr.strip()[-400:])
