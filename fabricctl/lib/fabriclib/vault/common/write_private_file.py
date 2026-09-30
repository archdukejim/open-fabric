import os


def write_private_file(path, data, uid=0, gid=0, mode=0o400):
    """Create or replace `path` atomically with `data` (str or bytes),
    owned by uid:gid with `mode`; the content is never world- or
    group-readable, not even for a moment."""
    tmp = f"{path}.tmp-{os.getpid()}"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        with os.fdopen(fd, "wb" if isinstance(data, bytes) else "w") as f:
            f.write(data)
        os.chown(tmp, uid, gid)
        os.chmod(tmp, mode)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
