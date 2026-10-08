from fabriclib.common.errors import ValidationError
from fabriclib.security.signin_layers import LAYERS, rank


def check_signin_lowering(current, wanted):
    """Purpose: setup never lowers a sign-in layer of an existing install (manual 5.8.2.6.4, D111): a --file or a
             re-run that would is refused, pointing to `fabricctl security lower`; a fresh install takes any values.
    Inputs:  current — the install's settings before this run ({} on a fresh install); wanted — the settings this run
             would save.
    Returns: None.
    Fails:   ValidationError naming the layer and the command, for any layer weaker in wanted than in current;
             ValidationError from rank for an unknown level.
    Feeds:   setup/collect_vars; tests/security."""
    if not current:
        return
    for layer, spec in LAYERS.items():
        key = spec["setting"]
        if key not in wanted:
            continue
        old = current.get(key) if spec["kind"] == "level" else bool(current.get(key))
        new = wanted.get(key) if spec["kind"] == "level" else bool(wanted.get(key))
        if rank(layer, new) < rank(layer, old):
            raise ValidationError(f"these settings would lower {layer} ({key}: {current.get(key)} -> "
                                  f"{wanted.get(key)}); setup never lowers a sign-in layer: run sudo fabricctl "
                                  f"security lower {layer} on this host instead")
