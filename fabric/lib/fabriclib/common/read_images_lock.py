import os

import yaml

LOCK = "images.lock.yaml"


def read_images_lock(fabric_dir):
    """The validated images of this fabric (<fabric_dir>/images.lock.yaml):
    {name: {var, repo, tag, digest, ref, …}} where ref is `repo:tag@digest`.
    Empty if the file is missing."""
    path = os.path.join(fabric_dir, LOCK)
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        images = (yaml.safe_load(f) or {}).get("images") or {}
    return {name: dict(e, ref=f"{e['repo']}:{e['tag']}@{e['digest']}") for name, e in images.items()}
