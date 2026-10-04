import os


def lock_dir(template_dir):
    """Purpose: the folder holding images.lock.yaml for a jinja folder: its parent on a host (fabric/), or the
             parent's config/ in a checkout (templates/ beside config/).
    Inputs:  template_dir — str, the jinja (templates) folder.
    Returns: str folder path; the parent when neither holds the lock (readers then treat the lock as missing).
    Fails:   never — existence checks only.
    Feeds:   jinja_env, deploy/verify_published_images."""
    parent = os.path.dirname(template_dir)
    if not os.path.exists(os.path.join(parent, "images.lock.yaml")) and os.path.isdir(os.path.join(parent, "config")):
        return os.path.join(parent, "config")
    return parent
