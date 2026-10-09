import urllib.parse

from webui.devpreview.sample_data import SAMPLE_DNS_FILTER


def dev_post_dns_filter(h, path, form):
    """Purpose: the DNS filter tab's changes acted out on the sample data in memory (nothing fetched or applied):
             lists added or removed (from the catalogue or by URL), names allowed or blocked, upstreams set.
    Inputs:  h — the dev handler (send); path — /dns-filter/…; form — dict.
    Returns: True when the path was handled (303 back to its section with a message); None otherwise.
    Fails:   never for form values (the dev preview checks little; fabriclib does in production).
    Feeds:   dev_post_action."""
    if not path.startswith("/dns-filter/"):
        return None
    what = "/".join(urllib.parse.unquote(p) for p in path.split("/")[2:])
    d, view = SAMPLE_DNS_FILTER, "lists"
    if what == "lists":
        url = form.get("url", "").strip()
        d["lists"].append({"name": form.get("name") or url, "url": url, "zone": "", "last_fetch": None,
                           "last_success": None, "rules": None, "skipped": None, "memory_mb": None, "error": None})
        d["catalogue"]["lists"] = [c for c in d["catalogue"]["lists"] if c["url"] != url]
        msg = f"{form.get('name') or url} added (dev preview: nothing fetched)."
    elif what == "lists/delete":
        d["lists"] = [i for i in d["lists"] if i["url"] != form.get("url")]
        msg = "List removed (in memory)."
    elif what == "fetch":
        msg = "Dev preview: nothing is fetched."
    elif what in ("rules", "rules/delete"):
        kind, name = form.get("kind"), form.get("name", "").strip().lower()
        own, other = (d["allow"], d["block"]) if kind == "allow" else (d["block"], d["allow"])
        if what == "rules":
            own.append(name) if name not in own else None
            other[:] = [n for n in other if n != name]
            msg = f"{name} {'allowed' if kind == 'allow' else 'blocked'} (in memory)."
        else:
            own[:] = [n for n in own if n != name]
            msg = f"{name} taken out of the rules (in memory)."
        view = form.get("back") or "rules"
    elif what == "upstreams":
        pairs = [p.split() for p in form.get("upstreams", "").replace("\n", ",").split(",") if p.strip()]
        d["upstreams"] = [] if form.get("upstreams", "").strip().lower() == "none" else \
            [{"address": p[0], "name": p[-1]} for p in pairs]
        msg, view = "Upstreams saved (in memory).", "settings"
    else:
        return None
    h.send(303, b"", location="/dns-filter?" + urllib.parse.urlencode({"view": view, "msg": msg}))
    return True
