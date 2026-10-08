import os

_PACKAGE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# static/ beside the package on a host (lib/webui/static); a checkout keeps it in static/webui-app (manual 1.2.2)
CSS_FILE = next((p for p in (os.path.join(_PACKAGE, "static", "app.css"),
                             os.path.join(_PACKAGE, "..", "..", "static", "webui-app",
                                          "app.css")) if os.path.exists(p)),
                os.path.join(_PACKAGE, "static", "app.css"))


def css():
    """Purpose: The whole stylesheet (static/webui-app/app.css), served as /static/app.css (light and dark colour
                schemes).
    Inputs:  none.
    Returns: CSS str (read once, then kept).
    Fails:   OSError if the file is missing (an incomplete install).
    Feeds:   src/webui/handler.Handler.handle_request (GET /static/app.css); devserver."""
    global _CSS
    try:
        return _CSS
    except NameError:
        _CSS = open(CSS_FILE).read()
        return _CSS
