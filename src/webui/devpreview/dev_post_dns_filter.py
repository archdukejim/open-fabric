import urllib.parse

from webui.devpreview.sample_data import SAMPLE_DNS_FILTER


def _target(d, group):
    """Purpose: where a change goes in the sample: everyone's settings or one group's.
    Inputs:  d — SAMPLE_DNS_FILTER; group — "" or a group's name.
    Returns: (dict with lists, allow, block; the label), or (None, label) for an unknown group.
    Fails:   never.
    Feeds:   dev_post_dns_filter."""
    if not group:
        return d, "everyone"
    return next((g for g in d["groups"] if g["name"] == group), None), f"group {group}"


def dev_post_dns_filter(h, path, form):
    """Purpose: the DNS filter tab's changes acted out on the sample data in memory (nothing fetched or applied):
             lists added or removed (from the catalogue or by URL), names allowed or blocked, for everyone or a
             client group; groups added, changed or removed; safe search; upstreams set.
    Inputs:  h — the dev handler (send); path — /dns-filter/…; form — dict.
    Returns: True when the path was handled (303 back to its section with a message); None otherwise.
    Fails:   never for form values (the dev preview checks little; fabriclib does in production).
    Feeds:   dev_post_action."""
    if not path.startswith("/dns-filter/"):
        return None
    what = "/".join(urllib.parse.unquote(p) for p in path.split("/")[2:])
    d = SAMPLE_DNS_FILTER
    group = form.get("group", "").strip()
    target, label = _target(d, group)
    view = form.get("back") or "lists"
    if target is None:
        err = f"no client group is called {group}"
        h.send(303, b"", location="/dns-filter?" + urllib.parse.urlencode({"view": view, "err": err}))
        return True
    if what == "lists":
        url = form.get("url", "").strip()
        target["lists"].append({"name": form.get("name") or url, "url": url, "zone": "", "last_fetch": None,
                                "last_success": None, "rules": None, "skipped": None, "memory_mb": None,
                                "error": None, "left_out": False})
        if not group:
            d["catalogue"]["lists"] = [c for c in d["catalogue"]["lists"] if c["url"] != url]
        msg = f"{form.get('name') or url} added for {label} (dev preview: nothing fetched)."
    elif what == "lists/delete":
        target["lists"] = [i for i in target["lists"] if i["url"] != form.get("url")]
        msg = f"List removed for {label} (in memory)."
    elif what == "fetch":
        msg = "Dev preview: nothing is fetched."
    elif what in ("rules", "rules/delete"):
        kind, name = form.get("kind"), form.get("name", "").strip().lower()
        own, other = (target["allow"], target["block"]) if kind == "allow" else (target["block"], target["allow"])
        if what == "rules":
            own.append(name) if name not in own else None
            other[:] = [n for n in other if n != name]
            msg = f"{name} {'allowed' if kind == 'allow' else 'blocked'} for {label} (in memory)."
        else:
            own[:] = [n for n in own if n != name]
            msg = f"{name} taken out of {label}'s rules (in memory)."
        view = form.get("back") or "rules"
    elif what == "groups":
        name, clients = form.get("name", "").strip().lower(), form.get("clients", "").replace(",", " ").split()
        g = next((x for x in d["groups"] if x["name"] == name), None)
        if g:
            g["clients"] = clients
        else:
            d["groups"].append({"name": name, "clients": clients, "safe_search": False, "youtube": "strict",
                                "lists": [], "allow": [], "block": []})
        msg, view = f"Group {name} {'changed' if g else 'added'} (in memory).", "groups"
    elif what == "groups/delete":
        d["groups"] = [x for x in d["groups"] if x["name"] != form.get("name")]
        msg, view = f"Group {form.get('name')} removed (in memory).", "groups"
    elif what == "safe-search":
        on, youtube = form.get("on") == "on", form.get("youtube") or "strict"
        if group:
            target["safe_search"], target["youtube"] = on, youtube
        else:
            d["safe_search"] = {"on": on, "youtube": youtube}
        msg = f"Strict safe search {'on' if on else 'off'} for {label} (in memory)."
        view = form.get("back") or "settings"
    elif what == "upstreams":
        pairs = [p.split() for p in form.get("upstreams", "").replace("\n", ",").split(",") if p.strip()]
        d["upstreams"] = [] if form.get("upstreams", "").strip().lower() == "none" else \
            [{"address": p[0], "name": p[-1]} for p in pairs]
        msg, view = "Upstreams saved (in memory).", "settings"
    else:
        return None
    h.send(303, b"", location="/dns-filter?" + urllib.parse.urlencode({"view": view, "msg": msg}))
    return True
