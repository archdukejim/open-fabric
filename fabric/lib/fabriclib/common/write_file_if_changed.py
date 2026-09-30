import os


def write_file_if_changed(path, text, mode, uid=0, gid=0):
    """Write `text` atomically with the given mode and owner, unless the file
    already holds exactly that. Returns True if it was written."""
    if os.path.exists(path) and open(path).read() == text:
        return False
    fd = os.open(path + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.chown(path + ".tmp", uid, gid)
    os.chmod(path + ".tmp", mode)
    os.replace(path + ".tmp", path)
    return True
