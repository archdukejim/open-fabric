from webui.views.constants import SERVICES
from webui.views.render_page import render_page


def overview(ctx, services):
    """Purpose: The Overview tab: one tile per service with a traffic light and a link to its tab.
    Inputs:  ctx — page context (webui/session/page_context); services — list of (name, systemd state, container health) from
             agentclient.service_status(); names are described via SERVICES.
    Returns: HTML str.
    Fails:   Jinja2 errors propagate (e.g. UndefinedError when the template reads an attribute of a value the caller
             left out).
    Feeds:   webui/routes/get_page (/); devserver; tests/webui/test_devserver.py.
    """
    return render_page("overview", ctx=ctx, tab="overview", services=services, service_info=SERVICES)
