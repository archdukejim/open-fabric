def relaxed_settings(vars_):
    """Purpose: the security relaxations this host has turned on, so `fabricctl status` and the web UI can show them
             while they are active (global Rule 10; manual 1.9.1). Host changes the admin declined are listed by
             consent_status instead.
    Inputs:  vars_ — the host's vars (image_signature_check).
    Returns: list of {"setting": str, "effect": str}; [] when none is relaxed.
    Fails:   never.
    Feeds:   system/show_relaxed_settings (`fabricctl status`); fabric-agent GET /v1/relaxed-settings (the web UI's
             Overview)."""
    relaxed = []
    if not vars_.get("image_signature_check", True):
        relaxed.append({"setting": "image_signature_check: false",
                        "effect": "fabric's published images are used without checking their signatures (2.6.3.4)"})
    return relaxed
