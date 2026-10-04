import os

import yaml

from fabriclib.consent.common.consent_file import consent_file


def load_consent(config_dir):
    """Purpose: the answers recorded for this install's host-change groups.
    Inputs:  config_dir — the install's config folder.
    Returns: {group: {"answer": "yes"|"no", "changes": [str, ...], "when": ISO time, "by": user}}; {} when nothing
             was asked yet. None when the install has no consent.yaml at all (an install set up before consent
             existed, or not set up).
    Fails:   yaml.YAMLError on a malformed file; OSError reading it.
    Feeds:   allowed_to_change, ask_consent, consent_status."""
    path = consent_file(config_dir)
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return (yaml.safe_load(f) or {}).get("groups") or {}
