import yaml


def compose_builds(compose_file):
    """Purpose: whether a rendered compose file builds its image (has a `build:` section) or pulls it (fabric's
             published images and upstream images, manual 1.14.3.3).
    Inputs:  compose_file — str, path of a rendered docker-compose.yml.
    Returns: bool.
    Fails:   OSError if unreadable; yaml.YAMLError on invalid YAML.
    Feeds:   install_service_units, finish_without_start, restart_changed (build or pull)."""
    with open(compose_file) as f:
        services = (yaml.safe_load(f) or {}).get("services") or {}
    return any("build" in (svc or {}) for svc in services.values())
