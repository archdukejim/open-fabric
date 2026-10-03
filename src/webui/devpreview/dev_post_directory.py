import urllib.parse

from webui import views
from webui.devpreview.fabric_rules import ValidationError, list_devices


def dev_post_directory(h, path, form):
    """Purpose: People, devices and roles acted out in memory, with the real fabriclib rules when available.
    Inputs:  h — the dev handler (send, state, ctx); path — /dirsrv/people/<_new|uid>[/reset] or
             /dirsrv/<devices|roles>/<name|_new>[/delete|/certs/…]; form — dict.
    Returns: True when the path was handled (a result page or a 303 with msg or err was sent); None otherwise (the
             device and role forms need fabriclib).
    Fails:   never for ValidationError (shown as err); other errors propagate.
    Feeds:   dev_post_action."""
    state, ctx = h.state, h.ctx
    if path.startswith("/dirsrv/people/"):
        name, op = (path.split("/")[3:] + ["", ""])[:2]
        users = state.data["people"]["users"]
        if name == "_new":
            uid = form.get("uid", "")
            if not uid or any(u["uid"] == uid for u in users):
                h.send(303, b"", location="/dirsrv?view=people&err=" + urllib.parse.quote(
                    f"{uid or 'a user name'} is missing or already exists"))
                return True
            users.append({"uid": uid, "name": f"{form.get('first', '')} {form.get('last', '')}".strip(),
                          "mail": form.get("email", ""), "locked": False, "groups": ["users"]})
            state.log("PERSON_CREATE", f"user={uid} (dev preview)")
            h.send(200, views.person_result(ctx, uid, "created", "dev-preview-not-real"))
            return True
        target = next((u for u in users if u["uid"] == name), None)
        if op != "reset" or not target:
            h.send(404, views.error_page(404, "Not found."))
            return True
        if set(target["groups"]) - {"users"} and "system:admin" not in ctx["perms"]:
            h.send(303, b"", location="/dirsrv?view=people&err=" + urllib.parse.quote(
                f"{name} is in a fabric group: only an admin can reset their sign-in"))
            return True
        state.log("PERSON_RESET", f"user={name} (dev preview)")
        h.send(200, views.person_result(ctx, name, "reset", "dev-preview-not-real"))
        return True
    if not (path.startswith("/dirsrv/") and list_devices):
        return None
    kind, name, op = (path.split("/")[2:] + ["", "", ""])[:3]
    d = state.data["directory"]
    try:
        if name == "_new":
            name = form.get("name", "").strip().lower()
            if any(x["name"] == name for x in d[kind]):
                raise ValidationError(f"{name} already exists")
            state.save(kind, name, form)
            back, msg = {"view": kind[:-1], "name": name}, f"{name} created (in memory)."
        elif op == "delete":
            if kind == "roles" and any(r["members"] for r in d["roles"] if r["name"] == name):
                raise ValidationError(f"role {name} still has devices; take them out first")
            d[kind] = [x for x in d[kind] if x["name"] != name]
            for r in d["roles"]:
                r["members"] = [m for m in r["members"] if m != name]
            back, msg = {"view": kind}, f"{name} deleted (in memory)."
        elif op == "certs":
            for x in d["devices"]:
                if x["name"] == name:
                    x["certs"] = [c for c in x["certs"] if c != form.get("sha256")]
            back, msg = {"view": "device", "name": name}, "Certificate unlinked (in memory)."
        else:
            state.save(kind, name, form)
            back, msg = {"view": kind[:-1], "name": name}, "Saved (in memory)."
        h.send(303, b"", location="/dirsrv?" + urllib.parse.urlencode({**back, "msg": msg}))
    except ValidationError as exc:
        back = {"view": kind} if name == "_new" or op == "delete" else {"view": kind[:-1], "name": name}
        h.send(303, b"", location="/dirsrv?" + urllib.parse.urlencode({**back, "err": str(exc)}))
    return True
