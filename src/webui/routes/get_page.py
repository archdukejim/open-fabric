from webui import agentclient as actions
from webui import views
from webui.routes.bind9_page import bind9_page
from webui.routes.dirsrv_page import dirsrv_page
from webui.routes.openbao_page import openbao_page
from webui.routes.stepca_page import stepca_page
from webui.session.page_context import page_context


def get_page(h, sess, path, query):
    """Purpose: Route a signed-in GET to its page.
    Inputs:  h — the request handler (send, deny); sess — dict from find_session; path — str: /, /bind9, /stepca,
             /dirsrv, /openbao, /kea, /freeradius, /audit; query — dict (view, zone, device, name, slot, msg, err as
             each page uses them).
    Returns: 200 page (overview with the host changes fabric may make, BIND9, Step-CA, directory, OpenBao, Kea,
             FreeRADIUS with its setup guides for view
             switches / windows, audit log).
    Fails:   404 for any other path; agent errors propagate to handle_request (400, redirect to /login, 403, 503).
    Feeds:   handler.Handler.handle_request.
    """
    ctx = page_context(sess)
    if path == "/":
        return h.send(200, views.overview(ctx, actions.service_status(), actions.host_changes(),
                                             actions.relaxed_settings()))
    if path == "/bind9":
        return bind9_page(h, ctx, query)
    if path == "/stepca":
        return stepca_page(h, ctx, query.get("view", "ca"), device=query.get("device", ""))
    if path == "/dirsrv":
        return dirsrv_page(h, ctx, query)
    if path == "/openbao":
        return openbao_page(h, ctx, query)
    if path == "/kea":
        return h.send(200, views.kea(ctx, actions.dhcp_overview(), query.get("msg", ""), query.get("err", "")))
    if path == "/freeradius":
        view = query.get("view", "overview")
        guides = actions.radius_guides() if view in ("switches", "windows") else None
        return h.send(200, views.freeradius(ctx, actions.radius_overview(), query.get("msg", ""),
                                            query.get("err", ""), view, guides))
    if path == "/audit":
        return h.send(200, views.audit(ctx, actions.read_audit()))
    return h.deny(404, "Not found.")
