from fabriclib.images.published_image import published_image


def effective_service(service, vars_, published):
    """Purpose: a managed service as this host runs it: when it runs fabric's published image (manual 1.14.3.3) its
             var is that image's (`image_fabric_<name>`) and it has no local build; otherwise unchanged.
    Inputs:  service — a SERVICES entry; vars_ — the host's vars; published — read_published_lock(...)["images"].
    Returns: dict, a copy of the entry (var and build replaced when the published image is in use).
    Fails:   never.
    Feeds:   installed_services (and so image_status, switch_image, update_images, rollback_image)."""
    entry = published.get(service.get("published") or "")
    if entry and published_image(vars_, entry):
        return dict(service, var=entry["var"], build=None)
    return dict(service)
