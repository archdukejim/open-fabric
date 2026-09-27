import os

from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.common.paths import DEPLOY_BASE_DIR
from fabriclib.common.save_vars import save_vars
from fabriclib.common.set_tsig_secrets import set_tsig_secrets
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit


def remove_tsig_key(actor, name, source="cli"):
    """Remove a TSIG key from vars.yaml, its secret from fabric-secrets.yml and
    the rfc2136.ini fabric wrote for it. Run apply afterwards; BIND then
    refuses updates signed with it."""
    with vars_lock():
        data = load_vars()
        keys = list(data.get("tsig_keys") or [])
        key = next((k for k in keys if k.get("name") == name), None)
        if key is None:
            raise ValidationError(f"no TSIG key named {name!r}")
        data["tsig_keys"] = [k for k in keys if k.get("name") != name]
        save_vars(data)
        set_tsig_secrets({name: None})
    ini = key.get("out") or os.path.join(DEPLOY_BASE_DIR, name, "rfc2136.ini")
    if os.path.basename(ini) == "rfc2136.ini" and os.path.isfile(ini):
        os.remove(ini)
        if os.path.dirname(ini) == os.path.join(DEPLOY_BASE_DIR, name) and not os.listdir(os.path.dirname(ini)):
            os.rmdir(os.path.dirname(ini))
    write_audit(actor, "TSIG_REMOVE", f"key={name}", source)
