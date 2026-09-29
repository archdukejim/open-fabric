import yaml

from fabriclib.images.built_from import built_from


def needs_rebuild(compose_file):
    """True if a service in this compose file builds a local image that is
    missing, was built FROM another base than its BASE_IMAGE build arg, or
    carries another pinned package version (a changed pin in images.lock.yaml)."""
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
