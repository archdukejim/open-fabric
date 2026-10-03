def service_user(v, name):
    """Purpose: look up the uid/gid a service's files must belong to.
    Inputs:  v — the rendered vars (reads service_users.<name>.uid/gid); name — str, e.g. "bind".
    Returns: (uid, gid) as ints; (0, 0) when the service is not listed.
    Fails:   ValueError/TypeError if a listed uid or gid is not a number.
    Feeds:   deploy/* (ownership of every deployed file and directory)."""
    svc = (v.get("service_users") or {}).get(name) or {}
    return int(svc.get("uid", 0)), int(svc.get("gid", 0))
