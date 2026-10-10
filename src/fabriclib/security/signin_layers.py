import json
import os

from fabriclib.common.errors import ValidationError
from fabriclib.keycloak.signin_levels import LEVELS, admin_level, signin_level

# The sign-in layers (manual 2.3.6.2.6.4, 2.1.6.24): raised in the web console's Security page (or `fabricctl security
# raise`), lowered only with `sudo fabricctl security lower` on the host. Kerberos is a way to sign in, not a layer:
# it changes both ways (`fabricctl security kerberos on|off`).
LAYERS = {
    "admin-2fa": {"setting": "signin_admin_second_factor", "kind": "level",
                  "what": "a second factor for the admin tools (the web console, OpenBao's UI, AdGuard's page)"},
    "everyone-2fa": {"setting": "signin_everyone_second_factor", "kind": "level",
                     "what": "a second factor for every sign-in (every app signing in through Keycloak)"},
    "client-cert": {"setting": "webui_client_cert", "kind": "switch",
                    "what": "a client certificate from fabric's CA for the web console"},
}
KERBEROS = "signin_kerberos"
LOWERED_FILE = "security-lowered.json"          # in the install's config folder: layers lowered below a level they had


def read_lowered(config_dir):
    """Purpose: the layers lowered below a level they had (LOWERED_FILE).
    Inputs:  config_dir — the install's config folder.
    Returns: dict {layer: {"from", "to", "by", "at"}}; {} without the file.
    Fails:   OSError / ValueError for an unreadable file.
    Feeds:   run_security_command, the agent's GET /v1/security, system/relaxed_settings."""
    path = os.path.join(config_dir, LOWERED_FILE)
    return json.load(open(path)) if os.path.exists(path) else {}


def on_off(text):
    """Purpose: a switch's value from what a person typed or a form sent.
    Inputs:  text — on/off, true/false, yes/no, 1/0 (any case), or a bool.
    Returns: bool.
    Fails:   ValidationError for anything else.
    Feeds:   layer_value, set_signin_layer (kerberos)."""
    word = str(text).strip().lower()
    if word in ("on", "true", "yes", "1"):
        return True
    if word in ("off", "false", "no", "0"):
        return False
    raise ValidationError(f"on or off (got {text!r})")


def layer_value(layer, text):
    """Purpose: a layer's value from what a person typed or a form sent.
    Inputs:  layer — a LAYERS key; text — a level name (none, any, totp, passkey) or, for a switch, on/off.
    Returns: str level, or bool for a switch.
    Fails:   ValidationError for an unknown layer or value.
    Feeds:   set_signin_layer, run_security_command, the agent's security route."""
    if layer not in LAYERS:
        raise ValidationError(f"unknown sign-in layer {layer!r} (one of {', '.join(LAYERS)})")
    if LAYERS[layer]["kind"] == "level":
        return signin_level(text)
    return on_off(text)


def rank(layer, value):
    """Purpose: how strong a layer's value is, to tell a raise from a lowering.
    Inputs:  layer — a LAYERS key; value — its value (level str or bool).
    Returns: int (higher is stronger): a level's place in LEVELS; a switch 1 on, 0 off.
    Fails:   ValidationError from signin_level for an unknown level.
    Feeds:   set_signin_layer, signin_rows, check_signin_lowering."""
    if LAYERS[layer]["kind"] == "level":
        return LEVELS.index(signin_level(value))
    return 1 if value else 0


def signin_rows(v, lowered):
    """Purpose: the sign-in layers as fabricctl security and the Security page show them.
    Inputs:  v — vars (the LAYERS settings, signin_kerberos); lowered — {layer: {"from", "to", "at", "by"}} from
             LOWERED_FILE.
    Returns: list of {"layer", "what", "value" (shown: a level, "on"/"off"), "effective" (the admin tools' level:
             never less than every sign-in's), "choices" (the stronger values: what raising offers), "lowered"
             (the entry, or None)} for each layer, then {"layer": "kerberos", "value": "on"/"off"}.
    Fails:   ValidationError from signin_level for a bad setting.
    Feeds:   run_security_command (status), the agent's GET /v1/security, relaxed_settings."""
    rows = []
    for layer, spec in LAYERS.items():
        value = v.get(spec["setting"])
        if spec["kind"] == "level":
            shown = signin_level(value)
            choices = [lvl for lvl in LEVELS if rank(layer, lvl) > rank(layer, shown)]
        else:
            shown, choices = ("on" if value else "off"), ([] if value else ["on"])
        effective = admin_level(v) if layer == "admin-2fa" else shown
        rows.append({"layer": layer, "what": spec["what"], "value": shown, "effective": effective,
                     "choices": choices, "lowered": lowered.get(layer)})
    rows.append({"layer": "kerberos", "what": "signing in with the domain logon (Kerberos)",
                 "value": "on" if v.get(KERBEROS, False) else "off", "effective": None, "choices": [], "lowered": None})
    return rows
