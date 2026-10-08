import json
import os

from fabriclib.common.paths import REVOKED_CERTS_FILE


def norm_serial(serial):
    """Purpose: a certificate serial as uppercase hex without colons or leading zeros, to compare serials.
    Inputs:  serial — str.
    Returns: str ("0" for zero).
    Fails:   never.
    Feeds:   revoked_serials, revoke_cert, list_issued."""
    return str(serial).replace(":", "").upper().lstrip("0") or "0"


def revoked_serials(path=REVOKED_CERTS_FILE):
    """Purpose: the serials revoked so far (manual 2.1.5.10).
    Inputs:  path — REVOKED_CERTS_FILE (JSON lines).
    Returns: set of normalised serials; empty without the file. Lines that do not parse are skipped.
    Fails:   OSError reading an existing file.
    Feeds:   revoke_cert, list_issued."""
    if not os.path.exists(path):
        return set()
    out = set()
    for line in open(path):
        try:
            out.add(norm_serial(json.loads(line)["serial"]))
        except (ValueError, KeyError):
            continue
    return out
