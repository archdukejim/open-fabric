from fabriclib.common.paths import AUDIT_FILE


def read_audit(limit=200, path=AUDIT_FILE):
    """The last `limit` audit lines, newest first."""
    try:
        with open(path) as f:
            return f.readlines()[-limit:][::-1]
    except FileNotFoundError:
        return []
