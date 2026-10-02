import os

import yaml

from fabriclib.common.paths import VARS_FILE


def load_vars(path=VARS_FILE):
    """Purpose: read vars.yaml.
    Inputs:  path — str, default VARS_FILE (<fabric>/config/vars.yaml).
    Returns: dict of the settings; {} if the file does not exist or is empty.
    Fails:   yaml.YAMLError on invalid YAML; OSError (e.g. PermissionError) if it cannot be read.
    Feeds:   dns/*, dhcp/add_reservation, dhcp/remove_reservation, radius/* (client and group edits),
             secrets/load_secrets, secrets/save_secrets, agent/ (fabric-agent), menu/ (the vars editor)."""
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}
