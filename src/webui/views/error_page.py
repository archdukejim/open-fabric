from webui.views.render_page import render_page


def error_page(status, message):
    """Purpose: The error page: status, message and a 'Sign in again' link.
    Inputs:  status — int HTTP status shown as the heading; message — str (autoescaped).
    Returns: HTML str, without header menu or tabs (no ctx).
    Fails:   never in practice (fixed template, two plain values).
    Feeds:   src/webui/handler.Handler.deny; devserver.
    """
    return render_page("error", status=status, message=message)
