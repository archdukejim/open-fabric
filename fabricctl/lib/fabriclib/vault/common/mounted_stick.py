import contextlib
import os
import subprocess

from fabriclib.common.errors import ValidationError


@contextlib.contextmanager
def mounted_stick(v, fs_path, name, writable=False):
    """Mount a key stick's file system for the duration of a `with` block at
    <openbao_runtime_dir>/../usb-<name> (a RAM path), read-only unless
    `writable`, always nosuid,nodev,noexec; unmount afterwards, whatever
    happens."""
    point = os.path.join(os.path.dirname(v["openbao_runtime_dir"].rstrip("/")), f"usb-{name}")
    os.makedirs(point, mode=0o700, exist_ok=True)
    opts = ("rw" if writable else "ro") + ",nosuid,nodev,noexec"
    res = subprocess.run(["mount", "-o", opts, fs_path, point], capture_output=True, text=True)
    if res.returncode != 0:
        raise ValidationError(f"cannot mount {fs_path}: {res.stderr.strip()[-200:]}")
    try:
        yield point
    finally:
        subprocess.run(["sync"], capture_output=True)
        subprocess.run(["umount", point], capture_output=True)
        try:
            os.rmdir(point)
        except OSError:
            pass
