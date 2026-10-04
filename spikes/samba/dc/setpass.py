"""S0 spike: set a domain user's password from a file, through Samba's own Python bindings (no argv secret).
Usage: setpass.py <smb.conf> <sAMAccountName> <password file>"""
import sys

from samba.auth import system_session
from samba.param import LoadParm
from samba.samdb import SamDB

conf, user, path = sys.argv[1:4]
lp = LoadParm()
lp.load(conf)
db = SamDB(url=lp.private_path("sam.ldb"), session_info=system_session(), lp=lp)
with open(path) as f:
    password = f.read().strip()
db.setpassword(f"(sAMAccountName={user})", password, force_change_at_next_login=False)
print(f"password set for {user}")
