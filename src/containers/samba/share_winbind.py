import os


def share_winbind(lp, gid):
    """Purpose: let FreeRADIUS (and only it) use winbind's privileged pipe, which `ntlm_auth` needs to have the DC
             check PEAP's MS-CHAPv2 answers (manual 1.6.5.17, S3.3; spike Q8): the pipe's folder in FreeRADIUS's
             group. Samba checks only the folder's owner (root) and mode (0750), so the group is fabric's to set.
    Inputs:  lp — LoadParm of the DC (its state directory); gid — int, FreeRADIUS's group id.
    Returns: list of str, what changed (empty when it already was so).
    Fails:   OSError from makedirs, chown or chmod.
    Feeds:   converge."""
    path = os.path.join(lp.get("state directory"), "winbindd_privileged")
    os.makedirs(path, mode=0o750, exist_ok=True)
    st = os.stat(path)
    if (st.st_uid, st.st_gid, st.st_mode & 0o7777) == (0, gid, 0o750):
        return []
    os.chown(path, 0, gid)
    os.chmod(path, 0o750)
    return [f"winbind's privileged pipe: group {gid}"]
