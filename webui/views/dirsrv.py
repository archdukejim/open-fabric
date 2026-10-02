from webui.views.constants import DIRSRV_SECTIONS
from webui.views.render_page import render_page


def dirsrv(ctx, view, data=None, people=None, device=None, role=None, msg="", err="", unavailable=""):
    """Purpose: The 389-DS tab: devices, one device, roles, one role, or people and groups.
    Inputs:  ctx — page context; view — 'devices' | 'device' | 'roles' | 'role' | 'people'; data — device_overview()
             dict (devices, roles, types, permissions), default empty; people — list_people() dict (users, groups,
             keycloak_url) for the people view; device / role — the item for the detail views; msg, err — flash
             texts; unavailable — why the directory could not be read (shown instead of the data).
    Returns: HTML str; the section tab is 'devices' for device and 'roles' for role.
    Fails:   Jinja2 errors propagate (e.g. UndefinedError when the template reads an attribute of a value the caller
             left out).
    Feeds:   webui/routes/dirsrv_page; devserver.
    """
    section = {"device": "devices", "role": "roles"}.get(view, view)
    return render_page("dirsrv", ctx=ctx, tab="dirsrv", view=view, section=section, sections=DIRSRV_SECTIONS,
                   data=data or {"devices": [], "roles": [], "types": [], "permissions": {}}, people=people,
                   device=device, role=role, msg=msg, err=err, unavailable=unavailable)
