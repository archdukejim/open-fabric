import datetime
import json
import os

from fabriclib.common.paths import ISSUED_CERTS_FILE


def record_issued(actor, kind, info, source="web", path=ISSUED_CERTS_FILE):
    """Purpose: Append one hand-issued certificate to the issued-certificate ledger (JSON lines),
             never its private key.
    Inputs:  actor — str, who issued it; kind — "csr" | "keypair"; info — describe_cert dict plus "device"
             (only subject, sans, serial, not_after, sha256, key and device are kept); source — "web"
             (default) | "cli"; path — the ledger, default ISSUED_CERTS_FILE
             (/opt/fabric/archive/issued-certs.jsonl): file created 0600, its directory 0700.
    Returns: None; the entry also carries "when" (local time, seconds).
    Fails:   OSError if the ledger or its directory cannot be created or written.
    Feeds:   issue_key_pair, sign_csr; read back by list_issued.
    """
    os.makedirs(os.path.dirname(path), mode=0o700, exist_ok=True)
    entry = {"when": datetime.datetime.now().isoformat(timespec="seconds"), "actor": actor, "source": source,
             "kind": kind, **{k: info.get(k) for k in ("subject", "sans", "serial", "not_after", "sha256", "key", "device")}}
    fd = os.open(path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
    with os.fdopen(fd, "a") as f:
        f.write(json.dumps(entry) + "\n")
