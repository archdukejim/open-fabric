from fabriclib.samba.gpo_request import gpo_request

LIMIT = 200          # a search shows at most this many policies (Microsoft's templates define thousands)


def gpo_overview(v, match="", container="samba"):
    """Purpose: what the Directory tab's Group Policy section shows (manual 1.6.5.21 S7.4, 4.6.8): the templates in
             the central store, what this site's admin settings and controls GPOs set, and — when searched — the
             matching policies.
    Inputs:  v — fabric vars (site_name); match — text to search policy names and titles for ("" lists none);
             container — the DC's container.
    Returns: {"site", "templates": [names], "settings": {"machine": [...], "user": [...]}, "controls" (the same
             shape), "match", "policies":
             [{template, name, display, class, elements}] (at most LIMIT), "more": bool (the search found more)}.
    Fails:   ValidationError from gpo_request (the DC not running, or the editor's refusal).
    Feeds:   agent routes GET /v1/gpo and POST /v1/gpo/search (domain:read)."""
    site = v["site_name"]
    found = gpo_request({"op": "policies", "match": match}, container) if match.strip() else []
    return {"site": site, "templates": gpo_request({"op": "templates"}, container),
            "settings": gpo_request({"op": "show", "site": site}, container),
            "controls": gpo_request({"op": "show", "site": site, "control": True}, container), "match": match,
            "policies": found[:LIMIT], "more": len(found) > LIMIT}
