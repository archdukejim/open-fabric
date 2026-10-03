import os
import shutil


def install_zone_file(src, dst, uid, gid):
    """Purpose: put a rendered zone file in place for BIND9 and drop its now-stale journal.
    Inputs:  src — rendered zone file; dst — deployed path; uid, gid — the bind user's ids.
    Returns: None; dst copied with a fresh mtime (so BIND sees it as newer on thaw/reload), mode 0640, and dst.jnl
             removed (a journal for the old file would make BIND refuse the zone: "journal out of sync").
    Fails:   OSError from the copy, chown or chmod.
    Feeds:   reload_zone; deploy/install_zones_and_restart (when BIND9 is stopped or about to restart)."""
    shutil.copy2(src, dst)
    # Fresh mtime: BIND reloads a zone file on thaw/reload only if it is newer
    # than what it loaded; copy2 kept the render time, often older than BIND's
    # own freeze-time write, so BIND kept serving the old zone (intermittent).
    os.utime(dst, None)
    os.chown(dst, uid, gid)
    os.chmod(dst, 0o640)
    # A journal written against the old file no longer matches it: BIND
    # would refuse to load the zone ("journal out of sync").
    if os.path.exists(dst + ".jnl"):
        os.remove(dst + ".jnl")
