import datetime
import json
import os

from fabriclib.common.paths import ISSUED_CERTS_FILE


def record_issued(actor, kind, info, source="web", path=ISSUED_CERTS_FILE):
    """Append a manually issued certificate to the ledger (no keys): who,
    how (csr | keypair), subject, names, serial, expiry, fingerprint, device."""
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    entry = {"when": datetime.datetime.now().isoformat(timespec="seconds"), "actor": actor, "source": source,
             "kind": kind, **{k: info.get(k) for k in ("subject", "sans", "serial", "not_after", "sha256", "key", "device")}}
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(fd, "a") as f:
        f.write(json.dumps(entry) + "\n")
