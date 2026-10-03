from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.federation.common.federation_lock import federation_lock
from fabriclib.federation.common.load_registry import load_registry
from fabriclib.federation.common.save_registry import save_registry


def drop_relay(actor, source="cli"):
    """Purpose: on a site that joined through a relay node: talk to its upstream directly from now on (the relay
             is gone or no longer wanted; design federation.md §6). Nothing else changes: the relay never held
             anything of the site.
    Inputs:  actor — str (audit); source — default "cli".
    Returns: the relay record that was dropped (dict: site, host, address, port).
    Fails:   ValidationError "this install has no upstream" / "this site does not use a relay"; OSError / yaml
             errors from the registry.
    Feeds:   run_federation_command (relay direct).
    Notes:   audited as FED_RELAY_DROP."""
    with federation_lock():
        registry = load_registry()
        up = registry["upstream"]
        if not up:
            raise ValidationError("this install has no upstream")
        relay = up.pop("relay", None)
        if not relay:
            raise ValidationError("this site does not use a relay")
        save_registry(registry)
    write_audit(actor, "FED_RELAY_DROP", f"relay={relay.get('site')} upstream={up.get('site_name')}", source)
    return relay
