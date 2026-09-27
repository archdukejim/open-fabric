import os
import re
import subprocess
import sys

from fabriclib.common.paths import LIB_DIR
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit


def apply_changes(actor, source="cli"):
    """Run the same apply as `fabricctl --apply`. Returns (ok, output)."""
    with vars_lock():
        res = subprocess.run([sys.executable, os.path.join(LIB_DIR, "interactive.py"), "--apply"],
                             capture_output=True, text=True, timeout=900,
                             env={**os.environ, "TERM": "dumb"})
    output = re.sub(r"\x1b\[[0-9;]*m", "", res.stdout + res.stderr)
    write_audit(actor, "APPLY", f"exit={res.returncode}", source)
    return res.returncode == 0, output
