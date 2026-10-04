import os

from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.common.paths import DEPLOY_BASE_DIR
from fabriclib.common.save_vars import save_vars
from fabriclib.common.set_tsig_secrets import set_tsig_secrets
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit
from fabriclib.dns.set_key_acls import set_key_acls


def remove_tsig_key(actor, name, source="cli"):
    """Purpose: Remove a TSIG key from vars.yaml and from every ACL, its secret from fabric's secrets, and the
             rfc2136.ini written for it. Run apply afterwards; BIND then refuses updates signed with it.
    Inputs:  actor — str, who asks (audit).
             name — str key name.
             source — "cli" (default) or "web". Reads/writes vars.yaml; removes the key's `out` file or
             <deploy_base>/<name>/rfc2136.ini.
    Returns: None.
    Fails:   ValidationError "no TSIG key named …"; errors from set_tsig_secrets (save_secrets) and set_key_acls;
             OSError removing the file; OSError or yaml.YAMLError from vars_lock / load_vars / save_vars / write_audit.
    Feeds:   agent route POST /v1/tsig/<name>/delete (fabric-agent, src/agent/); run_tsig_command (remove);
             tests/pki/run.py.
    Notes:   the file is deleted only if it is named rfc2136.ini, its folder only if that is <deploy_base>/<name> and
             now empty. The ACL clean-up is a second locked step (set_key_acls with drop_all).
    """
    with vars_lock():
        data = load_vars()
        keys = list(data.get("tsig_keys") or [])
        key = next((k for k in keys if k.get("name") == name), None)
        if key is None:
            raise ValidationError(f"no TSIG key named {name!r}")
        data["tsig_keys"] = [k for k in keys if k.get("name") != name]
        save_vars(data)
        set_tsig_secrets({name: None})
    set_key_acls(actor, name, drop_all=True, source=source)
    ini = key.get("out") or os.path.join(DEPLOY_BASE_DIR, name, "rfc2136.ini")
    if os.path.basename(ini) == "rfc2136.ini" and os.path.isfile(ini):
        os.remove(ini)
        if os.path.dirname(ini) == os.path.join(DEPLOY_BASE_DIR, name) and not os.listdir(os.path.dirname(ini)):
            os.rmdir(os.path.dirname(ini))
    write_audit(actor, "TSIG_REMOVE", f"key={name}", source)
