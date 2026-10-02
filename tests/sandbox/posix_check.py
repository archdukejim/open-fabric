"""Inside the sandbox: a person's POSIX attributes as 389-DS has them (read as Directory Manager over LDAPI in the
dirsrv container). Usage: python3 posix_check.py <uid> — prints uidNumber gidNumber homeDirectory loginShell."""
import subprocess
import sys

import yaml

v = yaml.safe_load(open("/opt/fabric/config/vars.yaml"))
code = f"""
import ldap, os
c = ldap.initialize("ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket")
c.simple_bind_s("cn=Directory Manager", os.environ["DS_DM_PASSWORD"])
a = c.search_s("uid={sys.argv[1]},ou=users,ou=accounts,{v['ldap_base_dn']}", ldap.SCOPE_BASE,
               attrlist=["uidNumber", "gidNumber", "homeDirectory", "loginShell"])[0][1]
print(" ".join((a.get(k) or [b"-"])[0].decode() for k in ("uidNumber", "gidNumber", "homeDirectory", "loginShell")))
"""
print(subprocess.run(["docker", "exec", "-i", "dirsrv", "python3", "-"], input=code, capture_output=True,
                     text=True).stdout.strip())
