import os
import re

SERIAL_RE = re.compile(r"^\s*\d+\s*;\s*Serial.*$", re.MULTILINE)


def zone_content_changed(src, dst):
    """Purpose: tell whether a rendered zone file differs from the deployed one, ignoring the SOA serial (which changes
             on every render).
    Inputs:  src — rendered zone file path; dst — deployed zone file path.
    Returns: True if dst is missing or the records differ, else False.
    Fails:   OSError if src (or an existing dst) cannot be read.
    Feeds:   find_changed_zones."""
    if not os.path.exists(dst):
        return True
    with open(src) as a, open(dst) as b:
        return SERIAL_RE.sub("", a.read()) != SERIAL_RE.sub("", b.read())
