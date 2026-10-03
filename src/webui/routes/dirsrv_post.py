import re
import urllib.parse

from webui import agentclient as actions
from webui import views
from webui.session.page_context import page_context


def _device_fields(form):
    """Purpose: Turn the device edit form into the fields fabric-agent's save_device takes.
    Inputs:  form — dict from read_form: type, owner, description, macs (space or comma separated), enabled (any
             non-empty value), role_<name> checkboxes.
    Returns: {'type': str, 'owner': str, 'description': str, 'macs': [str], 'enabled': bool, 'roles': [role names]}.
    Fails:   never.
    Feeds:   dirsrv_post → agentclient.save_device."""
    return {"type": form.get("type", ""), "owner": form.get("owner", ""), "description": form.get("description", ""),
            "macs": [m for m in re.split(r"[\s,]+", form.get("macs", "")) if m],
            "enabled": bool(form.get("enabled")),
            "roles": [k[5:] for k, val in form.items() if k.startswith("role_") and val]}


def _role_fields(form):
    """Purpose: Turn the role edit form into the fields fabric-agent's save_role takes.
    Inputs:  form — dict from read_form: description, vlan, priority, perm_<permission> checkboxes.
    Returns: {'description': str, 'vlan': str, 'priority': str, 'permissions': [permissions checked]}.
    Fails:   never.
    Feeds:   dirsrv_post → agentclient.save_role."""
    return {"description": form.get("description", ""), "vlan": form.get("vlan", ""),
            "priority": form.get("priority", ""),
            "permissions": [k[5:] for k, val in form.items() if k.startswith("perm_") and val]}


def dirsrv_post(h, sess, parts, form):
    """Purpose: Devices, device roles and people: each form maps to one fabric-agent call.
    Inputs:  h — the request handler (send, redirect, deny); sess — dict from find_session; parts — path segments after
             /dirsrv/: ['people', '_new'] (form uid, first, last, email), ['people', <uid>, 'reset'],
             ['devices'|'roles', '_new'] (form name + fields), ['devices'|'roles', <name>] (save), [..., <name>,
             'delete'], ['devices', <name>, 'certs', …] (unlink the certificate in form sha256); form — dict.
    Returns: people: 200 page with the one-time password; devices and roles: 303 to /dirsrv with msg — the new item's
             page after create, the list after delete, the item's page otherwise.
    Fails:   404 for an unknown kind or operation or a missing name; ValidationError → 303 with err (people list; the
             list after a failed create; else the item's page); AgentError, PermissionDenied and AuthError propagate.
    Feeds:   post_action (/dirsrv/…).
    Notes:   Only the third path segment is looked at, so any path under …/certs/ unlinks (the page posts to
             …/certs/unlink).
    """
    user = sess["user"]
    kind, name, op = (parts + ["", "", ""])[:3]
    if kind == "people":
        try:
            if name == "_new" and not op:
                uid, what = form.get("uid", ""), "created"
                password = actions.create_person(uid, form.get("first", ""), form.get("last", ""),
                                                 form.get("email", ""))
            elif name and op == "reset":
                uid, what = name, "reset"
                password = actions.reset_sign_in(uid)
            else:
                return h.deny(404, "Not found.")
        except actions.ValidationError as exc:
            return h.redirect("/dirsrv?" + urllib.parse.urlencode({"view": "people", "err": str(exc)}))
        return h.send(200, views.person_result(page_context(sess), uid, what, password))
    if kind not in ("devices", "roles") or not name:
        return h.deny(404, "Not found.")
    listing = {"view": kind}
    here = {"view": kind[:-1], "name": name}
    save, delete = ((actions.save_device, actions.delete_device) if kind == "devices"
                    else (actions.save_role, actions.delete_role))
    fields = _device_fields(form) if kind == "devices" else _role_fields(form)
    try:
        if name == "_new" and not op:
            created = save(user, form.get("name", ""), fields, new=True)["name"]
            back, msg = {"view": kind[:-1], "name": created}, f"{created} created."
        elif op == "delete":
            delete(user, name)
            back, msg = listing, f"{name} deleted."
        elif kind == "devices" and op == "certs":
            actions.link_device_cert(user, name, form.get("sha256", ""), link=False)
            back, msg = here, "Certificate unlinked."
        elif not op:
            save(user, name, fields)
            back, msg = here, "Saved."
        else:
            return h.deny(404, "Not found.")
        return h.redirect("/dirsrv?" + urllib.parse.urlencode({**back, "msg": msg}))
    except actions.ValidationError as exc:
        back = listing if name == "_new" else here
        return h.redirect("/dirsrv?" + urllib.parse.urlencode({**back, "err": str(exc)}))
