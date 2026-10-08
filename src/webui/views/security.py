from webui.views.render_page import render_page


def security(ctx, layers, msg="", err=""):
    """Purpose: the Security page (manual 5.8.2.6.4, D111): each sign-in layer, its state, and the raises it offers;
             lowering is shown as the host command, never as a button.
    Inputs:  ctx — page context; layers — security_layers(); msg, err — flash texts.
    Returns: HTML str.
    Fails:   never in practice (plain values).
    Feeds:   src/webui/routes/get_page (/security); devserver.
    """
    return render_page("security", ctx=ctx, tab="security", layers=layers, msg=msg, err=err)
