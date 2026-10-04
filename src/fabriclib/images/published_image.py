def published_image(vars_, entry):
    """Purpose: the one rule for whether a host runs fabric's published image or builds its own (manual 2.6.3.3):
             the published ref is in use when the host's var for it is set and the host's ids for the image's
             service account equal the ids baked into it (D80); an image with no account needs only the var.
    Inputs:  vars_ — mapping of the host's vars (a render context or ctx.vars): entry["var"] and service_users;
             entry — one image of read_published_lock(...)["images"] ({var, account?, ids?, …}).
    Returns: str, the published ref to run (pinned by digest); "" when the host builds the image itself.
    Fails:   never — missing vars or accounts mean "build locally".
    Feeds:   jinja_env (the published_ref template function), images/effective_service,
             deploy/verify_published_images."""
    ref = vars_.get(entry["var"]) or ""
    if not ref or "@sha256:" not in ref:
        return ""
    account = entry.get("account")
    if account:
        user = (vars_.get("service_users") or {}).get(account) or {}
        if f"{user.get('uid')}:{user.get('gid')}" != entry.get("ids"):
            return ""
    return ref
