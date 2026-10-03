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
    """Purpose: Add a TSIG key to vars.yaml (tsig_keys) and its secret to fabric's secrets (tsig_secrets). Run apply
             afterwards to render the key, its update-policy grants and its rfc2136.ini into BIND.
    Inputs:  actor — str, who asks (audit).
             entry — dict as in tsig_keys: name (required), domain, records, any_name, record_types, algorithm, primary,
             out, acls (see normalize_tsig_keys).
             secret — base64 str of an existing key, to keep its clients working; None for a new random 256-bit one.
             source — "cli" (default) or "web". Reads/writes vars.yaml under vars_lock; writes the secret through
             set_tsig_secrets (the 0600 file, or OpenBao once imported).
    Returns: (entry, secret): the normalized key dict as stored, and its base64 secret.
    Fails:   ValidationError "TSIG key … already exists", or one from normalize_tsig_keys (name, algorithm, domain,
             record types, record names, ACL names, "secret is not valid base64"); OSError or OpenBao errors from
             save_secrets; OSError or yaml.YAMLError from vars_lock / load_vars / save_vars / write_audit.
    Feeds:   create_zone_tsig_key (web UI), run_tsig_command (`fabricctl tsig add`).
    Notes:   the secret is saved before vars.yaml, so a failed save_vars leaves an unused secret behind.
    """
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
