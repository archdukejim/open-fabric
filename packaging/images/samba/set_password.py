"""Set a domain account's password from a file through Samba's own Python bindings (manual 1.6.5.5): the
password never reaches a command line or a process list.
    python3 set_password.py <smb.conf> <sAMAccountName> <password file>"""
import sys

from samba.auth import system_session
from samba.param import LoadParm
from samba.samdb import SamDB


def set_password(conf, account, path):
    """Purpose: set one account's password in the DC's own database.
    Inputs:  conf — str, the DC's smb.conf; account — str, sAMAccountName; path — str, a file holding the password
             (its first line; surrounding whitespace dropped).
    Returns: None.
    Fails:   OSError if a file cannot be read; ldb.LdbError if the account is missing or the password breaks the
             domain's policy.
    Feeds:   the image's entrypoint (the Administrator after provisioning)."""
    lp = LoadParm()
    lp.load(conf)
    db = SamDB(url=lp.private_path("sam.ldb"), session_info=system_session(), lp=lp)
    with open(path) as f:
        password = f.read().strip()
    db.setpassword(f"(sAMAccountName={account})", password, force_change_at_next_login=False)


if __name__ == "__main__":
    if len(sys.argv) != 4:
        sys.exit(__doc__)
    set_password(*sys.argv[1:4])
    print(f"password set for {sys.argv[2]}")
