import os
import subprocess
import sys

from fabriclib.common.paths import LIB_DIR, SECRETS_FILE, VARS_FILE
from fabriclib.system.apply_changes import apply_changes


def apply_signin(actor, source="cli"):
    """Purpose: make a sign-in change take effect (manual 2.3.6.2.6.4): the apply (nginx's client-certificate check, the
             web app's webui.json; nginx and the web UI restart when they changed), then fabric's Keycloak
             configuration (the sign-in flows, Kerberos).
    Inputs:  actor — who asked (audit, through apply_changes); source — "cli" or "web".
    Returns: (ok: bool, output: str) — ok when both succeeded; output is both steps' text.
    Fails:   subprocess.TimeoutExpired from apply_changes (900 s) or Keycloak's configuration (300 s); OSError.
    Feeds:   run_security_command (raise, lower, kerberos); fabric-agent POST /v1/security/raise."""
    ok, out = apply_changes(actor, source)
    if not ok:
        return False, out
    res = subprocess.run([sys.executable, os.path.join(LIB_DIR, "keycloak_bootstrap.py"), "--vars", VARS_FILE,
                          "--secrets", SECRETS_FILE], capture_output=True, text=True, timeout=300)
    return res.returncode == 0, out + res.stdout + res.stderr
