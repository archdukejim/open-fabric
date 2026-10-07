import datetime
import json
import os

from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.common.paths import VARS_FILE
from fabriclib.common.save_vars import save_vars
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit
from fabriclib.security.signin_layers import KERBEROS, LAYERS, LOWERED_FILE, layer_value, on_off, rank


def set_signin_layer(actor, layer, text, source="cli", lower=False, vars_file=VARS_FILE):
    """Purpose: change one sign-in layer in the install's settings (manual 5.8.2.6.4, D111): a raise from the web
             console or `fabricctl security raise`; a lowering only with lower=True (`fabricctl security lower`, after
             its typed confirmation). Kerberos (layer "kerberos", on/off) changes both ways. A lowering is recorded in
             LOWERED_FILE until the layer is raised back to what it had; every change is audited. The change takes
             effect with apply_signin.
    Inputs:  actor — who asks (audit; the web console's signed-in person, or root and the sudo user); layer — a LAYERS
             key or "kerberos"; text — the new value (a level, or on/off); source — "cli" or "web"; lower — True to
             allow a lowering; vars_file — the install's vars.yaml (tests: a scratch one).
    Returns: {"layer", "from", "to", "changed": bool} — values as shown (levels, "on"/"off").
    Fails:   ValidationError for an unknown layer or value, a lowering without lower=True ("lower it on the host with
             sudo fabricctl security lower …"), or lower=True for a change that is not a lowering; OSError / yaml
             errors from the vars file, the lowered file or the audit log.
    Feeds:   run_security_command (raise, lower, kerberos); fabric-agent POST /v1/security/raise (the Security page)."""
    with vars_lock():
        data = load_vars(vars_file)
        if layer == "kerberos":
            new, old = on_off(text), bool(data.get(KERBEROS, True))
            setting, direction = KERBEROS, "SET"
        else:
            new, setting = layer_value(layer, text), LAYERS[layer]["setting"]
            old = layer_value(layer, data.get(setting) if LAYERS[layer]["kind"] == "level" else bool(data.get(setting)))
            up, down = rank(layer, new) > rank(layer, old), rank(layer, new) < rank(layer, old)
            if down and not lower:
                raise ValidationError(f"lowering {layer} ({show(old)} to {show(new)}) is done only on the fabric host: "
                                      f"sudo fabricctl security lower {layer} {show(new)}")
            if lower and not down:
                raise ValidationError(f"{layer} is {show(old)}: {show(new)} is not a lowering")
            direction = "LOWER" if down else "RAISE" if up else "SET"
        changed = new != old
        if changed:
            data[setting] = new
            save_vars(data, vars_file)
            if layer != "kerberos":
                _mark(os.path.dirname(vars_file), layer, show(old), show(new), direction, actor)
    if changed:
        write_audit(actor, f"SECURITY_{direction}", f"{layer}: {show(old)} -> {show(new)}", source)
    return {"layer": layer, "from": show(old), "to": show(new), "changed": changed}


def show(value):
    """Purpose: a layer's value as people read it: a level as it is, a switch as on or off.
    Inputs:  value — a level (str) or a switch (bool).
    Returns: str.
    Fails:   never.
    Feeds:   set_signin_layer."""
    return value if isinstance(value, str) else ("on" if value else "off")


def _mark(config_dir, layer, old, new, direction, actor):
    """Purpose: keep LOWERED_FILE: a lowering is recorded with the level it had (the highest, when lowered twice); a
             raise back to that level or above clears it.
    Inputs:  config_dir — the install's config folder; layer — a LAYERS key; old, new — values as shown; direction —
             "LOWER", "RAISE" or "SET"; actor — who changed it.
    Returns: None.
    Fails:   OSError / ValueError reading or writing the file.
    Feeds:   set_signin_layer."""
    path = os.path.join(config_dir, LOWERED_FILE)
    lowered = json.load(open(path)) if os.path.exists(path) else {}
    entry = lowered.get(layer)
    if direction == "LOWER":
        top = entry["from"] if entry and rank(layer, layer_value(layer, entry["from"])) > rank(
            layer, layer_value(layer, old)) else old
        lowered[layer] = {"from": top, "to": new, "by": actor,
                          "at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")}
    elif entry and rank(layer, layer_value(layer, new)) >= rank(layer, layer_value(layer, entry["from"])):
        del lowered[layer]
    elif entry:
        entry["to"] = new
    with open(path + ".new", "w") as f:
        json.dump(lowered, f, indent=1)
    os.chmod(path + ".new", 0o644)
    os.replace(path + ".new", path)
