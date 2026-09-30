import os

import yaml

from fabriclib.common.read_images_lock import LOCK


def read_packages_lock(fabric_dir):
    """The pinned upstream packages fabric's own images install
    (<fabric_dir>/images.lock.yaml, `packages:`): {name: {version, repo,
    suite, key_url, key_fingerprint, …}}. Empty if the file is missing."""
    path = os.path.join(fabric_dir, LOCK)
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return (yaml.safe_load(f) or {}).get("packages") or {}
