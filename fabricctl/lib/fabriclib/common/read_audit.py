from fabriclib.common.paths import AUDIT_FILE


def read_audit(limit=200, path=AUDIT_FILE):
    """Purpose: the most recent audit log lines for display.
    Inputs:  limit — int, how many lines, default 200; path — str, default AUDIT_FILE.
    Returns: list of str lines (with their newlines), newest first; [] if the log does not exist.
    Fails:   OSError other than FileNotFoundError (e.g. PermissionError) propagates.
    Feeds:   agent/ (fabric-agent) (the audit route the web UI reads)."""
    try:
        with open(path) as f:
            return f.readlines()[-limit:][::-1]
    except FileNotFoundError:
        return []
