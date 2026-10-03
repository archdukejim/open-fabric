import os
import shutil

from fabriclib.common.keep_original import ORIGINALS


def restore_original(path, config_dir):
    """Purpose: put a host file back as it was before fabric first changed it (manual 2.7.1.5).
    Inputs:  path — the host file (absolute); config_dir — the install's config folder holding the record made by
             common/keep_original.
    Returns: "restored" (the copy or the symlink is back), "removed" (the file did not exist before fabric: it is
             gone again) or None (no record: fabric does not know what was there, nothing is touched). The record
             is removed once used.
    Fails:   OSError writing the host file.
    Feeds:   undo/undo_runtime, undo/undo_time, undo/undo_resolver."""
    store = os.path.join(config_dir, ORIGINALS, path.lstrip("/"))
    if os.path.exists(store + ".link"):
        with open(store + ".link") as f:
            target = f.read()
        if os.path.lexists(path):
            os.remove(path)
        os.symlink(target, path)
        os.remove(store + ".link")
        return "restored"
    if os.path.exists(store):
        if os.path.islink(path):
            os.remove(path)
        shutil.copy2(store, path)
        os.remove(store)
        return "restored"
    if os.path.exists(store + ".absent"):
        if os.path.lexists(path):
            os.remove(path)
        os.remove(store + ".absent")
        return "removed"
    return None
