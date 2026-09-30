import os
import pwd


def sudo_owner():
    """(login, home, uid, gid) of the account that ran `sudo fabricctl ...`,
    so files handed to the admin land in their home, owned by them; root when
    not run through sudo."""
    name = os.environ.get("SUDO_USER")
    try:
        p = pwd.getpwnam(name) if name and name != "root" else pwd.getpwuid(0)
    except KeyError:
        p = pwd.getpwuid(0)
    return p.pw_name, p.pw_dir, p.pw_uid, p.pw_gid
