import time

from webui.constants import LOGIN_COOKIE, LOGIN_TTL
from webui.httpio.cookie_header import cookie_header


def start_login(h, cert, next_path="/"):
    """Purpose: Start a Keycloak sign-in: remember the attempt (bound to this certificate) and send the browser to
             Keycloak.
    Inputs:  h — the request handler (app, redirect); cert — dict from verified_client_cert (fp is stored); next_path
             — str from ?next=, where to go after sign-in; anything that is not a local path (not starting with '/',
             starting with '//', or containing a backslash) becomes '/' (no open redirect).
    Returns: 303 to the Keycloak authorization URL, setting __Host-webui-login (the state, SameSite=Lax, 600 s);
             App.pending[state] gets nonce, verifier, fp, created, next.
    Fails:   never refuses.
    Feeds:   handler.Handler.handle_request (GET /login), reached from session failures and the vault step-up.
    Notes:   The login cookie is Lax because it must come back with the top-level redirect from Keycloak.
    """
    if not next_path.startswith("/") or next_path.startswith("//") or "\\" in next_path:
        next_path = "/"
    url, state, nonce, verifier = h.app.oidc.start_login()
    with h.app.lock:
        h.app.pending[state] = {"nonce": nonce, "verifier": verifier, "fp": cert["fp"], "created": time.time(),
                                "next": next_path}
    h.redirect(url, [cookie_header(LOGIN_COOKIE, state, LOGIN_TTL, "Lax")])
