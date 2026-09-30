import datetime
import os
import syslog

from fabriclib.common.paths import AUDIT_FILE


def write_audit(actor, action, detail, source="cli", path=AUDIT_FILE):
    """Purpose: append one audit line — who (actor and source), what, details — to the audit log and the
             journal (identifier fabric-audit, facility authpriv) where the optional log forwarder picks it up.
    Inputs:  actor — str, the acting user; action — str, e.g. "IMAGE_UPDATE"; detail — str; source — str,
             "cli" by default (also "web", …); path — str, default AUDIT_FILE (its folder is created 0700).
             Carriage returns and newlines are replaced by spaces so one call is one line.
    Returns: None.
    Fails:   OSError if the log folder or file cannot be written. Journal errors are ignored.
    Feeds:   nearly every change operation (dns, dhcp, ldap, keycloak, pki, radius, vault, images/switch_image,
             system/apply_changes, secrets), agent/server.py and interactive.py."""
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    line = f"[{stamp}] User: {actor} ({source}) | Action: {action} | {detail}"
    line = line.replace("\r", " ").replace("\n", " ")
    with open(path, "a") as f:
        f.write(line + "\n")
    try:
        syslog.openlog("fabric-audit", 0, syslog.LOG_AUTHPRIV)
        syslog.syslog(syslog.LOG_NOTICE, line)
    except OSError:
        pass
