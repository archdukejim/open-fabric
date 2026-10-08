import os

from fabriclib.common.lock_dir import lock_dir
from fabriclib.common.read_published_lock import read_published_lock
from fabriclib.images.published_image import published_image
from fabriclib.images.verify_signature import verify_signature


def verify_published_images(paths, final_vars):
    """Purpose: before anything is installed, check the signature of every published fabric image this deploy will
             run (decisions 2.1.14.6, 2.1.14.10; manual 1.14.3.4); a refusal stops the deploy with nothing changed.
    Inputs:  paths — deploy_paths() (jinja: where the lock is found; render: the rendered compose files, so only
             services this host runs count); final_vars — rendered vars (image_fabric_*, service_users,
             image_cosign, image_signature_check).
    Returns: list of str refs checked (verified now or remembered); [] when the check is off or none is in use.
    Fails:   ValidationError from verify_signature for an image it refuses.
    Feeds:   apply_deployment."""
    if not final_vars.get("image_signature_check", True):
        return []
    lock = read_published_lock(lock_dir(paths["jinja"]))
    checked = []
    for name, entry in sorted((lock.get("images") or {}).items()):
        ref = published_image(final_vars, entry)
        if ref and os.path.exists(os.path.join(paths["render"], name, "docker-compose.yml")):
            verify_signature(ref, final_vars["image_cosign"], lock["signer"], lock["issuer"])
            checked.append(ref)
    return checked
