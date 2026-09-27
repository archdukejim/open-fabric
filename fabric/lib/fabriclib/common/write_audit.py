import datetime
import os

from fabriclib.common.paths import AUDIT_FILE


def write_audit(actor, action, detail, source="cli", path=AUDIT_FILE):
    """Append one audit line: who (actor + source), what, details."""
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    stamp = datetime.datetime.now().isoformat(timespec="seconds")
    line = f"[{stamp}] User: {actor} ({source}) | Action: {action} | {detail}"
    with open(path, "a") as f:
        f.write(line.replace("\r", " ").replace("\n", " ") + "\n")
