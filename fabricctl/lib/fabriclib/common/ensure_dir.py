import os


def ensure_dir(path, mode=0o750, uid=0, gid=0):
    """Purpose: make sure a directory exists with the given mode and owner (created if missing, fixed if not).
    Inputs:  path — str; mode — int, default 0o750; uid, gid — int, default 0 (root).
    Returns: None.
    Fails:   OSError (PermissionError when not root, FileExistsError if path is a file) from os.makedirs/chmod/chown.
    Feeds:   deploy/* (archive, web, service, OpenBao, BIND9, dirsrv, webui, Step-CA and data directories)."""
    if not os.path.exists(path):
        os.makedirs(path, mode=mode)
    os.chmod(path, mode)
    os.chown(path, uid, gid)
