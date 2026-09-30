import yaml

from fabriclib.images.built_from import built_from


def needs_rebuild(compose_file):
    """Purpose: whether a compose file's locally built image must be rebuilt: missing, built FROM another
             base than its BASE_IMAGE build arg, or (Kea) built with another pinned KEA_VERSION.
    Inputs:  compose_file — str, path to a rendered docker-compose.yml. Asks Docker via built_from.
    Returns: bool; False when no service has a build section with BASE_IMAGE or KEA_VERSION.
    Fails:   OSError if the file cannot be read; yaml.YAMLError on invalid YAML; AttributeError if a service's
             `build` is a plain string rather than a mapping.
    Feeds:   deploy.py (decides whether to run `docker compose build`)."""
    with open(compose_file) as f:
        services = (yaml.safe_load(f) or {}).get("services") or {}
    for svc in services.values():
        args = (svc.get("build") or {}).get("args") or {}
        base = args.get("BASE_IMAGE")
        if base and built_from(svc.get("image", "")) != base:
            return True
        # a pinned upstream package (e.g. KEA_VERSION) changed: its label differs
        if args.get("KEA_VERSION") and built_from(svc.get("image", ""), "org.fabric.kea") != args["KEA_VERSION"]:
            return True
    return False
