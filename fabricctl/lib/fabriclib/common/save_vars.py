import yaml

from fabriclib.common.paths import VARS_FILE


def _empty_to_null(data):
    """Purpose: turn every empty string in a nested structure into None so it is saved as YAML null.
    Inputs:  data — any: dicts and lists are walked recursively, other values kept.
    Returns: a new structure of the same shape with "" replaced by None.
    Fails:   never (RecursionError only for a self-containing structure).
    Feeds:   save_vars."""
    if isinstance(data, dict):
        return {k: _empty_to_null(v) for k, v in data.items()}
    if isinstance(data, list):
        return [_empty_to_null(v) for v in data]
    return None if data == "" else data


def save_vars(data, path=VARS_FILE):
    """Purpose: write vars.yaml, empty strings stored as null, keys in their given order.
    Inputs:  data — dict of settings; path — str, default VARS_FILE. Callers hold vars_lock.
    Returns: None.
    Fails:   OSError if the file cannot be written; yaml.representer.RepresenterError for values YAML cannot dump.
             Not atomic: the file is truncated first, so a failure mid-write leaves it partial.
    Feeds:   dns/* (record, ACL and TSIG edits), dhcp/add_reservation, dhcp/remove_reservation,
             radius/add_radius_client, remove_radius_client, map_radius_group, unmap_radius_group."""
    with open(path, "w") as f:
        yaml.dump(_empty_to_null(data), f, default_flow_style=False, sort_keys=False)
