import os

import yaml

from fabriclib.common.paths import FEDERATION_FILE


def save_registry(registry, path=FEDERATION_FILE):
    """Purpose: write the federation record atomically (a temp file renamed over it), 0640.
    Inputs:  registry — {"sites": {...}, "upstream": {...} or None} (load_registry's shape); path — default
             FEDERATION_FILE. Callers hold federation_lock.
    Returns: None.
    Fails:   OSError; yaml.representer.RepresenterError for values YAML cannot dump.
    Feeds:   accept_join, join_upstream."""
    os.makedirs(os.path.dirname(path), mode=0o750, exist_ok=True)
    tmp = path + ".tmp"
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o640)
    with os.fdopen(fd, "w") as f:
        yaml.safe_dump({"sites": registry.get("sites") or {}, "upstream": registry.get("upstream")}, f,
                       sort_keys=True)
    os.replace(tmp, path)
