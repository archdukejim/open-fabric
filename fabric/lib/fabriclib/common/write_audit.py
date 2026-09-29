import datetime
import os
import syslog

from fabriclib.common.paths import AUDIT_FILE


def write_audit(actor, action, detail, source="cli", path=AUDIT_FILE):
    """Append one audit line: who (actor + source), what, details. The line
    also goes to the journal (identifier fabric-audit), where the optional
    log forwarder picks it up."""
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
