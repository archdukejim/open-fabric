import datetime
import json
import os

from fabriclib.common.paths import ISSUED_CERTS_FILE

SOON = datetime.timedelta(days=30)


def list_issued(limit=200, path=ISSUED_CERTS_FILE, now=None):
    """Purpose: The hand-issued certificates from the ledger, newest first, each with its expiry status.
    Inputs:  limit — maximum entries, default 200; path — the ledger, default ISSUED_CERTS_FILE;
             now — timezone-aware datetime (tests), default the current UTC time.
    Returns: list of ledger entries (when, actor, source, kind, subject, sans, serial, not_after, sha256,
             key, device) each plus "status": "valid" | "expires soon" (under 30 days) | "expired";
             [] when there is no ledger. Lines that do not parse are skipped.
    Fails:   OSError if the ledger exists but cannot be read.
    Feeds:   agent route GET /v1/pki/issued -> webui agentclient.list_issued -> PKI page (issued view).
    """
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
