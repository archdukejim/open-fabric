import base64
import os

from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.common.set_tsig_secrets import set_tsig_secrets
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit
from fabriclib.dns.normalize_tsig_keys import normalize_tsig_keys


def replace_tsig_secret(actor, name, secret=None, source="cli"):
    """Purpose: Give an existing TSIG key a new secret. Run apply afterwards; clients holding the old secret are then
             refused.
    Inputs:  actor — str, who asks (audit).
             name — str key name.
             secret — base64 str (e.g. the one an existing client already uses); None or "" for a freshly generated
             256-bit one.
             source — "cli" (default) or "web". Reads vars.yaml under vars_lock; writes through set_tsig_secrets.
    Returns: the base64 secret now in force (str).
    Fails:   ValidationError "no TSIG key named …" or "…: secret is not valid base64" (from normalize_tsig_keys); errors
             from save_secrets; OSError or yaml.YAMLError from the vars helpers.
    Feeds:   rotate_tsig_key; run_tsig_command (set-secret, rotate).
    """
    new = secret or base64.b64encode(os.urandom(32)).decode()
    with vars_lock():
        data = load_vars()
        key = next((k for k in data.get("tsig_keys") or [] if k.get("name") == name), None)
        if key is None:
            raise ValidationError(f"no TSIG key named {name!r}")
        _, embedded = normalize_tsig_keys([dict(key, secret=new)], data.get("domain", ""))   # validates base64
        set_tsig_secrets(embedded)
    write_audit(actor, "TSIG_SECRET", f"key={name} {'given' if secret else 'regenerated'}", source)
    return new
