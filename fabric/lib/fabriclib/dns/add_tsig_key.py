import base64
import os

from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.common.save_vars import save_vars
from fabriclib.common.set_tsig_secrets import set_tsig_secrets
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit
from fabriclib.dns.normalize_tsig_keys import normalize_tsig_keys


def add_tsig_key(actor, entry, secret=None, source="cli"):
    """Add a TSIG key to vars.yaml and its secret to fabric-secrets.yml.
    `entry` as in tsig_keys (name, domain, records, record_types, algorithm,
    out); `secret`: an existing key's base64 secret to keep its clients
    working, else a new 256-bit one. Run apply afterwards to render it into
    BIND (key, update-policy grants, rfc2136.ini). Returns (entry, secret)."""
    with vars_lock():
        data = load_vars()
        keys = list(data.get("tsig_keys") or [])
        if any(k.get("name") == entry.get("name") for k in keys):
            raise ValidationError(f"TSIG key {entry.get('name')!r} already exists")
        new = dict(entry, secret=secret or base64.b64encode(os.urandom(32)).decode())
        normalized, embedded = normalize_tsig_keys(keys + [new], data.get("domain", ""))
        data["tsig_keys"] = normalized
        set_tsig_secrets(embedded)
        save_vars(data)
    added = normalized[-1]
    write_audit(actor, "TSIG_ADD", f"key={added['name']} domain={added['domain']} "
                                   f"records={added.get('records') or 'zone'} types={added['record_types']}", source)
    return added, embedded[added["name"]]
