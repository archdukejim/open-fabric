import os
import re
import subprocess
import sys

from fabriclib.common.paths import LIB_DIR
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit


def apply_changes(actor, source="cli"):
    """Purpose: re-render, deploy and reload changed services exactly like `fabricctl --apply`, under the vars
             lock, and audit it.
    Inputs:  actor — who asked (audit log); source — "cli" (default) or "web".
    Returns: (ok: bool, output: str) — ok when `interactive.py --apply` exited 0; output is its stdout+stderr
             without colour codes. An APPLY audit entry with the exit code is written either way.
    Fails:   subprocess.TimeoutExpired after 900 s (no audit entry then); OSError from the lock or audit log.
    Feeds:   fabric-agent (agent/ (fabric-agent), source "web"); dns run_tsig_command and run_acl_command,
             dhcp run_dhcp_command, radius run_radius_command."""
    with vars_lock():
        res = subprocess.run([sys.executable, os.path.join(LIB_DIR, "interactive.py"), "--apply"],
                             capture_output=True, text=True, timeout=900,
                             env={**os.environ, "TERM": "dumb"})
    output = re.sub(r"\x1b\[[0-9;]*m", "", res.stdout + res.stderr)
    write_audit(actor, "APPLY", f"exit={res.returncode}", source)
    return res.returncode == 0, output
