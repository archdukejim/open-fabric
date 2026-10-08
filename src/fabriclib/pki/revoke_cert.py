import datetime
import json
import os
import re

from fabriclib.common.errors import ValidationError
from fabriclib.common.paths import ISSUED_CERTS_FILE, REVOKED_CERTS_FILE
from fabriclib.common.write_audit import write_audit
from fabriclib.pki.common.revoked_serials import norm_serial, revoked_serials
from fabriclib.pki.list_issued import list_issued
from fabriclib.pki.pick_up_cert import pick_up_cert
from fabriclib.pki.publish_crl import REASONS, publish_crl

SERIAL_RE = re.compile(r"^(?:[0-9A-Fa-f]{2}:?){1,20}$")


def _issuer_of(entry):
    """Purpose: which of this install's CAs signed a ledger entry: the root for a site's CA it signed flat, the
             intermediate for everything else (leaves, and a site nested under this one).
    Inputs:  entry — a ledger entry (kind, issuer).
    Returns: "root" or "intermediate".
    Fails:   never.
    Feeds:   revoke_cert."""
    if entry.get("kind") != "site-ca":
        return "intermediate"
    return "intermediate" if "Intermediate" in (entry.get("issuer") or "") else "root"


def revoke_cert(v, actor, target, reason="unspecified", source="cli", ledger=ISSUED_CERTS_FILE,
                revoked=REVOKED_CERTS_FILE, publish=True):
    """Purpose: revoke a certificate fabric issued (manual 2.1.5.10): record it and publish the CRLs at once, so
             FreeRADIUS and the web console refuse it even while a device is still linked.
    Inputs:  v — settings; actor — who (audit); target — a serial (hex, colons allowed) or a name: the subject's CN of
             one certificate in the issued-certificate ledger; reason — one of REASONS; source — "cli" | "web";
             ledger, revoked, publish — for tests.
    Returns: {"serial", "subject", "issuer", "reason"} of the revoked certificate.
    Fails:   ValidationError: an unknown reason; a target that is neither a serial nor a name in the ledger, or a name
             matching several certificates (use the serial); a certificate already revoked; a site CA signed by the
             root on a host without the root key (its CRL cannot be signed here). subprocess.CalledProcessError
             from publish_crl or from reloading nginx / restarting FreeRADIUS.
    Feeds:   cli (`fabricctl certs revoke`), agent route POST /v1/pki/revoke, people/remove_person (their
             certificates)."""
    if reason not in REASONS:
        raise ValidationError(f"unknown reason {reason!r}: one of {', '.join(REASONS)}")
    target = (target or "").strip()
    entries = list_issued(limit=1000000, path=ledger)
    if SERIAL_RE.match(target) and not any(e.get("subject", "").endswith(f"CN={target}") for e in entries):
        found = [e for e in entries if norm_serial(str(e.get("serial", ""))) == norm_serial(target)]
        entry = found[0] if found else {"serial": target, "subject": "(not in the ledger: issued over ACME or by "
                                                                    "step-ca)", "kind": "leaf"}
    else:
        found = [e for e in entries if re.search(rf"(^|,)CN={re.escape(target)}(,|$)", e.get("subject") or "")]
        live = [e for e in found if e.get("status") != "expired"]
        if not found:
            raise ValidationError(f"no certificate named {target!r} in the issued-certificate ledger: give its serial "
                                  "(fabricctl certs issued, or the web console's PKI page)")
        if len(live) > 1:
            raise ValidationError(f"{len(live)} certificates are named {target!r}: give the serial of the one to "
                                  "revoke (" + ", ".join(str(e.get('serial')) for e in live) + ")")
        entry = (live or found)[0]
    serial = norm_serial(str(entry["serial"]))
    if serial in revoked_serials(revoked):
        raise ValidationError(f"certificate {serial} is already revoked")
    issuer = _issuer_of(entry)
    secrets = os.path.join(v["deploy_base_dir"], "stepca", "data", "secrets")
    if issuer == "root" and not os.path.exists(os.path.join(secrets, "root_ca_key")):
        raise ValidationError("this site CA was signed by the root, whose key is not on this host (a brought-in "
                              "root): revoke it where the root key is")
    record = {"serial": serial, "when": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
              "actor": actor, "source": source, "reason": reason, "issuer": issuer,
              "subject": entry.get("subject", ""), "not_after": entry.get("not_after", "")}
    os.makedirs(os.path.dirname(revoked), mode=0o700, exist_ok=True)
    fd = os.open(revoked, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(fd, "a") as f:
        f.write(json.dumps(record) + "\n")
    write_audit(actor, "PKI_REVOKE", f"serial={serial} subject={record['subject']} reason={reason}", source)
    if publish:                              # in force at once: nginx reloads, FreeRADIUS restarts (seconds)
        crl = publish_crl(v, revoked_file=revoked)
        if crl["changed"]:
            pick_up_cert("nginx")
        if crl["radius_changed"]:
            pick_up_cert("freeradius")
    return {k: record[k] for k in ("serial", "subject", "issuer", "reason")}
