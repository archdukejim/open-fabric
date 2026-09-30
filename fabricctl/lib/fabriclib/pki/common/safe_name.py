import re


def safe_name(cn):
    """A file name for downloads derived from a certificate name."""
    return re.sub(r"[^A-Za-z0-9._-]", "-", cn).strip(".-") or "certificate"
