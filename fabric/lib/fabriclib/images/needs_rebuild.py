import yaml

from fabriclib.images.built_from import built_from


def needs_rebuild(compose_file):
    """True if a service in this compose file builds a local image that is
    missing or was built FROM another base than its BASE_IMAGE build arg
    (a changed pin in images.lock.yaml / vars)."""
    with open(compose_file) as f:
        services = (yaml.safe_load(f) or {}).get("services") or {}
    for svc in services.values():
        base = ((svc.get("build") or {}).get("args") or {}).get("BASE_IMAGE")
        if base and built_from(svc.get("image", "")) != base:
            return True
    return False
