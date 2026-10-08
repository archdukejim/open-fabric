import os

import yaml

from fabriclib.common.read_images_lock import LOCK


def read_published_lock(fabric_dir):
    """Purpose: fabric's own published images as the lock pins them (`published:` in images.lock.yaml, manual 1.14.3).
    Inputs:  fabric_dir — str, folder holding images.lock.yaml (the install, or the checkout's config/).
    Returns: dict {"registry", "signer", "issuer", "images": {name: {var, tag, digest, account?, ids?, repo, ref}}},
             where repo is "<registry>/<name>" and ref "repo:tag@digest", or "" while the image is not published
             (no digest); {} if the file or the section is missing.
    Fails:   yaml.YAMLError on invalid YAML; KeyError if the section lacks registry or an image lacks var;
             OSError if unreadable.
    Feeds:   jinja_env (published_lock global and the published_ref function), images/published_image callers,
             images/verify_signature, images/prune_images; tests/images."""
    path = os.path.join(fabric_dir, LOCK)
    if not os.path.exists(path):
        return {}
    with open(path) as f:
        section = (yaml.safe_load(f) or {}).get("published") or {}
    if not section:
        return {}
    images = {}
    for name, e in (section.get("images") or {}).items():
        repo = f"{section['registry']}/{name}"
        ref = f"{repo}:{e.get('tag') or 'latest'}@{e['digest']}" if e.get("digest") else ""
        images[name] = dict(e, var=e["var"], repo=repo, ref=ref)
    return dict(section, images=images)
