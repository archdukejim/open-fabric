import os
import pwd


def sudo_owner():
    """Purpose: the account that ran `sudo fabricctl …`, so files handed to the admin land in their home,
             owned by them.
    Inputs:  none. Reads SUDO_USER from the environment and the passwd database.
    Returns: tuple (login str, home str, uid int, gid int); root's when not run through sudo, SUDO_USER is root,
             or SUDO_USER is not a known account.
    Fails:   never in practice — only KeyError if uid 0 itself is missing from passwd.
    Feeds:   pki/hand_out_client_cert, pki/mint_extra_cert, setup/create_admin, setup/run_uninstall_command,
             setup/setup_openbao, setup/verify_install."""
    name = os.environ.get("SUDO_USER")
    try:
        p = pwd.getpwnam(name) if name and name != "root" else pwd.getpwuid(0)
    except KeyError:
        p = pwd.getpwuid(0)
    return p.pw_name, p.pw_dir, p.pw_uid, p.pw_gid
