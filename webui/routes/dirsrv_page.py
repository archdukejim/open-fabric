from webui import agentclient as actions
from webui import views


def dirsrv_page(h, ctx, query, status=200):
    """Purpose: Render the 389-DS tab: devices, one device, roles, one role, or people.
    Inputs:  h — the request handler (send); ctx — page context; query — dict: view ('device', 'roles', 'role',
             'people', else 'devices'), name (device or role; unknown → the list), msg, err; status — int, default 200.
    Returns: the directory page with the given status; when the directory cannot be read (AgentError,
             ValidationError) the page shows why instead of the data.
    Fails:   PermissionDenied and AuthError propagate to handle_request (403, redirect to /login).
    Feeds:   get_page (/dirsrv).
    """
    view = query.get("view") if query.get("view") in ("device", "roles", "role", "people") else "devices"
    kw = {"msg": query.get("msg", ""), "err": query.get("err", "")}
    try:
        if view == "people":
            return h.send(status, views.dirsrv(ctx, view, people=actions.list_people(), **kw))
        data = actions.device_overview()
    except (actions.AgentError, actions.ValidationError) as exc:
        return h.send(status, views.dirsrv(ctx, view, unavailable=str(exc), **kw))
    if view == "device":
        kw["device"] = next((d for d in data["devices"] if d["name"] == query.get("name")), None)
        view = view if kw["device"] else "devices"
    if view == "role":
        kw["role"] = next((r for r in data["roles"] if r["name"] == query.get("name")), None)
        view = view if kw["role"] else "roles"
    return h.send(status, views.dirsrv(ctx, view, data=data, **kw))
