import datetime
import glob
import json
import os

from fabriclib.common.paths import CERT_RENEWAL_FILE, ISSUED_CERTS_FILE
from fabriclib.pki.list_issued import list_issued
from fabriclib.pki.common.cert_dates import cert_dates

SERVICE_DAYS_LEFT = 7          # a service certificate this close: renewal has been failing (2.1.5.4)
CA_DAYS_LEFT = 180             # the root or intermediate CA (2.1.5.5): replacing it is a manual procedure
# where the service certificates are, under the deploy base (mint_service_certs' destinations)
SERVICE_CERTS = ["nginx/certs/*/fullchain.pem", "bind9/ssl/fullchain.pem", "openbao/certs/fullchain.pem",
                 "keycloak/certs/fullchain.pem", "postgres/certs/fullchain.pem", "samba/tls/fullchain.pem",
                 "freeradius/certs/server.pem"]


def _left(path, now):
    """Purpose: days until a certificate expires.
    Inputs:  path — PEM file; now — aware datetime.
    Returns: float days, or None when it cannot be read.
    Fails:   never.
    Feeds:   cert_warnings."""
    dates = cert_dates(path)
    return None if dates is None else (dates[1] - now).total_seconds() / 86400


def cert_warnings(v, now=None, record=CERT_RENEWAL_FILE, ledger=ISSUED_CERTS_FILE):
    """Purpose: what is wrong or coming with fabric's certificates (manual 2.1.5.4, 2.1.5.5), for `fabricctl status`,
             `fabricctl doctor` and the web console's Overview.
    Inputs:  v — settings (deploy_base_dir); now — for tests; record — the last renewal run (CERT_RENEWAL_FILE);
             ledger — the issued-certificate ledger.
    Returns: list of {"level": "fail" | "warn", "what": str}: the last renewal run failed (fail); a service
             certificate with under 7 days left or unreadable (fail); the root or intermediate CA within 180 days
             (warn); issued certificates (people, devices, the web console's client certificates) expiring
             within 30 days or expired in the last 30 (warn, counted). [] when all is well.
    Fails:   never (an unreadable record or ledger is a warning).
    Feeds:   cli (`fabricctl status`), setup/verify_install (doctor), agent route GET /v1/cert-warnings."""
    now = now or datetime.datetime.now(datetime.timezone.utc)
    base = v.get("deploy_base_dir", "/opt")
    out = []
    if os.path.exists(record):
        try:
            last = json.load(open(record))
            if not last.get("ok", True):
                out.append({"level": "fail", "what": f"the certificate renewal of {last.get('when', '?')} failed: "
                                                     f"{last.get('error', '')} (sudo fabricctl certs to retry)"})
        except (OSError, ValueError):
            out.append({"level": "warn", "what": f"the last certificate renewal's record cannot be read ({record})"})
    for pattern in SERVICE_CERTS:
        for path in sorted(glob.glob(os.path.join(base, pattern))):
            left = _left(path, now)
            name = os.path.relpath(path, base)
            if left is None:
                out.append({"level": "fail", "what": f"{name}: the certificate cannot be read"})
            elif left < SERVICE_DAYS_LEFT:
                out.append({"level": "fail", "what": f"{name}: {max(left, 0):.0f} day(s) left — renewal is not "
                                                     "working (sudo fabricctl certs; see journalctl -u fabric-certs)"})
    certs = os.path.join(base, "stepca", "data", "certs")
    for name, label in (("root_ca.crt", "the root CA"), ("intermediate_ca.crt", "the intermediate CA")):
        left = _left(os.path.join(certs, name), now) if os.path.exists(os.path.join(certs, name)) else None
        if left is not None and left < CA_DAYS_LEFT:
            out.append({"level": "warn", "what": f"{label} expires in {max(left, 0):.0f} day(s): plan its "
                                                 "replacement (manual 3.5)"})
    try:
        issued = list_issued(limit=100000, path=ledger, now=now)
    except OSError:
        issued = []
        out.append({"level": "warn", "what": f"the issued-certificate ledger cannot be read ({ledger})"})
    soon = sum(e["status"] == "expires soon" for e in issued)
    gone = sum(e["status"] == "expired" and now - datetime.datetime.strptime(e["not_after"], "%b %d %H:%M:%S %Y %Z")
               .replace(tzinfo=datetime.timezone.utc) < datetime.timedelta(days=30) for e in issued)
    if soon or gone:
        out.append({"level": "warn", "what": f"issued certificates: {soon} expiring within 30 days, {gone} expired "
                                             "in the last 30 days (the web console's PKI page lists them)"})
    return out
