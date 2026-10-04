import os

import yaml

LOCK = "images.lock.yaml"


def read_images_lock(fabric_dir):
    """Purpose: the validated, digest-pinned images of this fabric.
    Inputs:  fabric_dir — str, folder holding images.lock.yaml (the install, or the checkout's config/).
    Returns: dict {name: {var, repo, tag, digest, …, ref}} where ref is "repo:tag@digest"; {} if the file is missing.
    Fails:   yaml.YAMLError on invalid YAML; KeyError if an entry lacks repo, tag or digest; OSError if unreadable.
    Feeds:   jinja_env (images_lock global), images/image_status, images/prune_images; tests/image_ref.py,
             tests/render.py and several suites."""
    path = os.path.join(fabric_dir, LOCK)
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        images = (yaml.safe_load(f) or {}).get("images") or {}
    return {name: dict(e, ref=f"{e['repo']}:{e['tag']}@{e['digest']}") for name, e in images.items()}
