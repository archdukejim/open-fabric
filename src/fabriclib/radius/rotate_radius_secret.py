import secrets as _random
import string

from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit
from fabriclib.radius.normalize_radius_clients import SECRET_RE
from fabriclib.secrets.save_secrets import save_secrets


def rotate_radius_secret(actor, name, secret=None, source="cli"):
    """Purpose: Give a RADIUS client a new shared secret, kept in fabric's secrets. Applied by the next apply; until the
             device has the same secret, FreeRADIUS does not answer it.
    Inputs:  actor — str, who asks (audit).
             name — str (lower-cased).
             secret — str matching SECRET_RE, or None for a random 32-character one.
             source — "cli" (default) or "web". Reads vars.yaml under vars_lock.
    Returns: the secret (str), to be shown once.
    Fails:   ValidationError "the secret must be 16-128 printable characters, …", "no RADIUS client …"; errors from
             save_secrets; OSError or yaml.YAMLError from the vars helpers.
    Feeds:   agent route POST /v1/radius/clients/<name>/rotate (fabric-agent, src/agent/, called by
             the web UI); run_radius_command (rotate-secret).
    """
    name = str(name).strip().lower()
    if secret is not None and not SECRET_RE.match(secret):
        raise ValidationError("the secret must be 16-128 printable characters, "
                              "without spaces, quotes, backslashes or $")
    secret = secret or "".join(_random.choice(string.ascii_letters + string.digits) for _ in range(32))
    with vars_lock():
        if not any(c.get("name") == name for c in load_vars().get("radius_clients") or []):
            raise ValidationError(f"no RADIUS client {name}")
        save_secrets({"radius_secrets": {name: secret}})
    write_audit(actor, "RADIUS_CLIENT_ROTATE", f"client={name}", source)
    return secret
