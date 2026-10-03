import os

CSS_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "static", "app.css")


def css():
    """Purpose: The whole stylesheet (webui/static/app.css), served as /static/app.css (light and dark colour schemes).
    Inputs:  none.
    Returns: CSS str (read once, then kept).
    Fails:   OSError if the file is missing (an incomplete install).
    Feeds:   webui/handler.Handler.handle_request (GET /static/app.css); devserver."""
    global _CSS
    try:
        return _CSS
    except NameError:
        _CSS = open(CSS_FILE).read()
        return _CSS
