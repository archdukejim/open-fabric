import os

import yaml

from fabriclib.common.paths import VARS_FILE


def load_vars(path=VARS_FILE):
    """Read vars.yaml; an empty dict if it does not exist."""
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return yaml.safe_load(f) or {}
