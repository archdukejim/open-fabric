import os


def write_file_if_changed(path, text, mode, uid=0, gid=0):
    """Purpose: write a file atomically with the given mode and owner, unless it already holds exactly
             that text.
    Inputs:  path — str; text — str; mode — int permission bits; uid, gid — int owner, default root.
    Returns: True if the file was written, False if it already had that content (mode and owner not checked then).
    Fails:   OSError from reading, writing, chown (needs root for another owner) or rename; a stale <path>.tmp
             is left behind if a step after its creation fails.
    Feeds:   dhcp/deploy_kea, radius/deploy_freeradius, setup/mint_service_certs."""
    if os.path.exists(path) and open(path).read() == text:
        return False
    fd = os.open(path + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.chown(path + ".tmp", uid, gid)
    os.chmod(path + ".tmp", mode)
    os.replace(path + ".tmp", path)
    return True
