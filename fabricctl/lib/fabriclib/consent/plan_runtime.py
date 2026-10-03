from fabriclib.security.hardened_daemon_settings import DAEMON_JSON, hardened_daemon_settings


def plan_runtime(v):
    """Purpose: what hardening Docker's daemon changes (design host-consent.md §2 `runtime`).
    Inputs:  v — vars: security.docker_daemon_hardening (default True).
    Returns: list of str: each daemon.json key that changes, then the Docker restart it needs (which restarts
             every container on the host, not only fabric's); [] when off or already hardened.
    Fails:   json.JSONDecodeError / OSError from hardened_daemon_settings.
    Feeds:   consent/plan_host_changes, setup/harden_docker."""
    if not (v.get("security") or {}).get("docker_daemon_hardening", True):
        return []
    current, merged = hardened_daemon_settings()
    keys = [k for k in merged if merged[k] != current.get(k)]
    if not keys:
        return []
    return [f"{DAEMON_JSON}: set {k} = {merged[k]}" for k in keys] + \
        ["restart Docker to apply it: every container on this host restarts once, not only fabric's"]
