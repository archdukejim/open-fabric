import os

from fabriclib.common.paths import VARS_FILE
from fabriclib.keycloak.signin_levels import admin_level
from fabriclib.security.signin_layers import read_lowered


def relaxed_settings(vars_, config_dir=None):
    """Purpose: the security relaxations this host has turned on, so `fabricctl status` and the web UI can show them
             while they are active (global Rule 10; manual 1.9.1). Host changes the admin declined are listed by
             consent_status instead.
    Inputs:  vars_ — the host's vars (image_signature_check, the sign-in settings); config_dir — the install's config
             folder (LOWERED_FILE: sign-in layers lowered with `fabricctl security lower`; default vars.yaml's).
    Returns: list of {"setting": str, "effect": str}; [] when none is relaxed.
    Fails:   OSError / ValueError for an unreadable LOWERED_FILE.
    Feeds:   system/show_relaxed_settings (`fabricctl status`); fabric-agent GET /v1/relaxed-settings (the web UI's
             Overview)."""
    relaxed = []
    if not vars_.get("image_signature_check", True):
        relaxed.append({"setting": "image_signature_check: false",
                        "effect": "fabric's published images are used without checking their signatures (2.6.3.4)"})
    if vars_.get("install_keycloak") and admin_level(vars_) == "none":     # D110: a password only, by default
        relaxed.append({"setting": "signin_admin_second_factor: none",
                        "effect": "the web console, OpenBao and AdGuard's page ask for a password only; raise a "
                                  "second factor in the web console's Security page (5.8.2.6)"})
    for layer, entry in read_lowered(config_dir or os.path.dirname(VARS_FILE)).items():
        relaxed.append({"setting": f"{layer} lowered: {entry['from']} -> {entry['to']}",
                        "effect": f"lowered by {entry['by']} on {entry['at']} (fabricctl security lower); raise it "
                                  "again in the Security page"})
    return relaxed
