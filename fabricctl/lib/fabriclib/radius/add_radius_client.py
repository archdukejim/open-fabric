import secrets as _random
import string

from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.common.save_vars import save_vars
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit
from fabriclib.radius.normalize_radius_clients import normalize_radius_clients
from fabriclib.secrets.save_secrets import save_secrets


def add_radius_client(actor, name, address, message_authenticator=True, secret=None, source="cli"):
    """Add a switch or access point that may ask FreeRADIUS (vars.yaml
    radius_clients) and keep its shared secret in OpenBao: `secret` (one the
    device already has) or a new random one. Applied by the next apply.
    Returns the secret, to be shown once."""
    secret = secret or "".join(_random.choice(string.ascii_letters + string.digits) for _ in range(32))
    with vars_lock():
        data = load_vars()
        if not data.get("install_freeradius"):
            raise ValidationError("802.1X is off (install_freeradius: false)")
        current = data.get("radius_clients") or []
        clients, _ = normalize_radius_clients(current + [{"name": name, "address": address, "secret": secret,
                                                          "message_authenticator": message_authenticator}])
        save_secrets({"radius_secrets": {clients[-1]["name"]: secret}})
        data["radius_clients"] = clients
        save_vars(data)
    c = clients[-1]
    write_audit(actor, "RADIUS_CLIENT_ADD", f"client={c['name']} address={c['address']} "
                                            f"message_authenticator={c['message_authenticator']}", source)
    return secret
