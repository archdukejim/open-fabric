import glob
import os


def wipe_runtime_keys(v):
    """Once OpenBao is unsealed it holds its key in memory: overwrite and
    delete the copies fabric-unlock left in <openbao_runtime_dir>. Returns
    how many were wiped."""
    count = 0
    for path in glob.glob(os.path.join(v["openbao_runtime_dir"], "*.key")):
        try:
            os.chmod(path, 0o600)
            with open(path, "r+b") as f:
                f.write(b"\0" * max(os.path.getsize(path), 1))
                f.flush()
                os.fsync(f.fileno())
            os.remove(path)
            count += 1
        except FileNotFoundError:
            pass
    return count
