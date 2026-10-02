from webui.views.render_page import render_page


def continue_page(target):
    """Purpose: The 'Signed in' page that moves on to the target with a meta refresh and a link.
    Inputs:  target — str local path to continue to (webui/session/start_login allows only local paths).
    Returns: HTML str.
    Fails:   never in practice (fixed template, one plain value).
    Feeds:   webui/session/finish_login.
    """
    return render_page("continue", target=target)
