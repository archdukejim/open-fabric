import glob
import os


def wipe_runtime_keys(v):
    """Purpose: once OpenBao is unsealed (it holds its key in memory), overwrite and delete the key copies that
             fabric-unlock left in RAM.
    Inputs:  v — vars: openbao_runtime_dir; every *.key in it is wiped (zeros, fsync, delete).
    Returns: how many files were wiped (int).
    Fails:   OSError other than FileNotFoundError (e.g. not root); a file that vanished meanwhile is skipped.
    Feeds:   `fabricctl vault wipe-key` (the openbao unit, after start), rotate_vault_key, setup/setup_openbao,
             tests/openbao/run.py.
    """
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
