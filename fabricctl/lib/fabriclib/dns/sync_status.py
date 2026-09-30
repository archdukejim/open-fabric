import os
import re
import subprocess

from fabriclib.common.paths import BIND_DATA_DIR


def sync_status(zone, data_dir=BIND_DATA_DIR):
    """Purpose: Compare the serial BIND is serving for a zone with the deployed zone file.
    Inputs:  zone — str zone name.
             data_dir — folder holding db.<zone> (default BIND_DATA_DIR). Runs `docker exec -u bind bind9 rndc
             zonestatus <zone>` (10 s timeout).
    Returns: (state, message): state is "in_sync", "out_of_sync" (serving an older serial than the file), "not_loaded"
             or "unreachable".
    Fails:   OSError if the zone file exists but cannot be read; a missing docker binary or a timeout gives
             "unreachable".
    Feeds:   zone_detail; fabricctl/lib/interactive.py (zone editor header).
    Notes:   a zone file without a "; Serial" line counts as in sync once BIND serves the zone.
    """
    file_serial = None
    zone_file = os.path.join(data_dir, f"db.{zone}")
    if os.path.exists(zone_file):
        with open(zone_file) as f:
            m = re.search(r"^\s*(\d+)\s*;\s*Serial", f.read(), re.MULTILINE)
            file_serial = m.group(1) if m else None
    try:
        res = subprocess.run(["docker", "exec", "-u", "bind", "bind9", "rndc", "zonestatus", zone],
                             capture_output=True, text=True, timeout=10)
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return "unreachable", "BIND9 not reachable"
    m = re.search(r"^serial:\s*(\d+)", res.stdout, re.MULTILINE)
    if res.returncode != 0 or not m:
        return "not_loaded", "not loaded in BIND9"
    live = m.group(1)
    if file_serial and int(live) < int(file_serial):
        return "out_of_sync", f"out of sync (serving serial {live}, file has {file_serial}; apply to publish)"
    return "in_sync", f"in sync (serial {live})"
