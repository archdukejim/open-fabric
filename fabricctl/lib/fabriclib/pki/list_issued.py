import datetime
import json
import os

from fabriclib.common.paths import ISSUED_CERTS_FILE

SOON = datetime.timedelta(days=30)


def list_issued(limit=200, path=ISSUED_CERTS_FILE, now=None):
    """Certificates issued by hand (CSR signing, generated key pairs), newest
    first, each with status 'valid' | 'expires soon' | 'expired'."""
    if not os.path.exists(path):
        return []
    now = now or datetime.datetime.now(datetime.timezone.utc)
    out = []
    with open(path) as f:
        for line in f:
            try:
                entry = json.loads(line)
                end = datetime.datetime.strptime(entry["not_after"], "%b %d %H:%M:%S %Y %Z").replace(
                    tzinfo=datetime.timezone.utc)
            except (ValueError, KeyError, TypeError):
                continue
            entry["status"] = "expired" if end < now else ("expires soon" if end - now < SOON else "valid")
            out.append(entry)
    return out[::-1][:limit]
