from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.common.save_vars import save_vars
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit
from fabriclib.secrets.save_secrets import save_secrets


def remove_radius_client(actor, name, source="cli"):
    """Remove a RADIUS client and delete its secret; FreeRADIUS stops
    answering it at the next apply."""
    name = str(name).strip().lower()
    with vars_lock():
        data = load_vars()
        clients = data.get("radius_clients") or []
        kept = [c for c in clients if c.get("name") != name]
        if len(kept) == len(clients):
            raise ValidationError(f"no RADIUS client {name}")
        data["radius_clients"] = kept
        save_vars(data)
        save_secrets({"radius_secrets": {name: None}})
    write_audit(actor, "RADIUS_CLIENT_REMOVE", f"client={name}", source)
