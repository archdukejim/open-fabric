import os

from fabriclib.common.paths import FABRIC_DIR


def version_info():
    """Purpose: the installed fabric version and build stamp.
    Inputs:  none (reads VERSION and BUILD in FABRIC_DIR, the tree this code runs from).
    Returns: {"version": VERSION content or "unknown", "build": BUILD content or ""}.
    Fails:   never for missing files; OSError for other read errors.
    Feeds:   fabric-agent (agent/server.py) for the web UI."""
    def read(name):
        try:
            with open(os.path.join(FABRIC_DIR, name)) as f:
                return f.read().strip()
        except FileNotFoundError:
            return ""
    return {"version": read("VERSION") or "unknown", "build": read("BUILD")}
