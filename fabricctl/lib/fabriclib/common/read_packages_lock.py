import os

import yaml

from fabriclib.common.read_images_lock import LOCK


def read_packages_lock(fabric_dir):
    """Purpose: the pinned upstream packages fabric's own images install (`packages:` in images.lock.yaml).
    Inputs:  fabric_dir — str, folder holding images.lock.yaml.
    Returns: dict {name: {version, repo, suite, key_url, key_fingerprint, …}}; {} if the file or section is missing.
    Fails:   yaml.YAMLError on invalid YAML; OSError if unreadable.
    Feeds:   jinja_env (packages_lock global, used by the kea templates); tests/kea/run.py."""
    path = os.path.join(fabric_dir, LOCK)
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        return (yaml.safe_load(f) or {}).get("packages") or {}
