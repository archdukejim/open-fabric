from fabriclib.consent.groups import GROUPS
from fabriclib.consent.load_consent import load_consent


def consent_status(config_dir):
    """Purpose: this install's answers to the host-change questions, for `fabricctl status` and the web UI (manual 2.7.1.4, step 7): what fabric may change on the host, and what declining left unmanaged.
    Inputs:  config_dir — the install's config folder.
    Returns: list of {"group", "title", "state": "approved"|"declined"|"not asked", "when", "by", "relaxation"
             (the consequence when declined, else "")}, in GROUPS order; [] for an install set up before consent
             existed (no consent.yaml).
    Fails:   yaml.YAMLError / OSError from load_consent.
    Feeds:   show_consent_status (`fabricctl status`); fabric-agent GET /v1/host-changes (the web UI's Overview)."""
    groups = load_consent(config_dir)
    if groups is None:
        return []
    rows = []
    for group, meta in GROUPS.items():
        rec = groups.get(group) or {}
        state = {"yes": "approved", "no": "declined"}.get(rec.get("answer"), "not asked")
        rows.append({"group": group, "title": meta["title"], "state": state, "when": rec.get("when", ""),
                     "by": rec.get("by", ""), "relaxation": meta["declined"] if state == "declined" else ""})
    return rows
