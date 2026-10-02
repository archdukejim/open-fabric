import os

from fabriclib.dns.zone_content_changed import zone_content_changed


def find_changed_zones(src_dir, dst_dir):
    """Purpose: find the rendered zone files (db.<zone>) whose records differ from the deployed ones.
    Inputs:  src_dir — rendered bind9/data directory; dst_dir — deployed bind9/data directory.
    Returns: [(zone, src, dst)] for each changed zone, sorted by file name; [] if src_dir does not exist.
    Fails:   OSError if a file cannot be read (from zone_content_changed).
    Feeds:   deploy/install_bind9_files (the zones installed or reloaded later); tests/zone_test.py.
    Notes:   copies nothing: installing is done by install_zone_file / reload_zone."""
    changed = []
    if not os.path.isdir(src_dir):
        return changed
    for fname in sorted(os.listdir(src_dir)):
        if not fname.startswith("db."):
            continue
        src, dst = os.path.join(src_dir, fname), os.path.join(dst_dir, fname)
        if zone_content_changed(src, dst):
            changed.append((fname[3:], src, dst))
    return changed
