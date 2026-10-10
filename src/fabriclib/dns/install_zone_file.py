import os
import shutil

from fabriclib.dns.merge_dynamic_records import merge_dynamic_records

REVERSE = (".in-addr.arpa", ".ip6.arpa")


def install_zone_file(src, dst, uid, gid):
    """Purpose: put a rendered zone file in place for BIND9 and drop its now-stale journal.
    Inputs:  src — rendered zone file; dst — deployed path (db.<zone>); uid, gid — the bind user's ids.
    Returns: None; dst copied with a fresh mtime (so BIND sees it as newer on thaw/reload), mode 0640, and dst.jnl
             removed (a journal for the old file would make BIND refuse the zone: "journal out of sync"). For a reverse
             zone the PTR and DHCID records Kea wrote into the file being replaced are kept (merge_dynamic_records,
             2.1.10.7): callers freeze a running BIND first, so that file holds them.
    Fails:   OSError from the copy, read, write, chown or chmod.
    Feeds:   reload_zone; deploy/finish_without_start and deploy/restart_changed (BIND stopped or about to restart)."""
    zone = os.path.basename(dst)[3:] if os.path.basename(dst).startswith("db.") else ""
    if zone.endswith(REVERSE) and os.path.exists(dst):
        with open(src) as f:
            new = f.read()
        with open(dst) as f:
            merged = merge_dynamic_records(zone, new, f.read())
        with open(dst, "w") as f:
            f.write(merged)
    else:
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
