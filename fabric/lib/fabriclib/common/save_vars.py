import yaml

from fabriclib.common.paths import VARS_FILE


def _empty_to_null(data):
    if isinstance(data, dict):
        return {k: _empty_to_null(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_empty_to_null(v) for v in data]
    return None if data == "" else data


def save_vars(data, path=VARS_FILE):
    """Write vars.yaml; empty strings are stored as null."""
    with open(path, "w") as f:
        yaml.dump(_empty_to_null(data), f, default_flow_style=False, sort_keys=False)
