import hmac
import time

from webui.constants import REFRESH_BEFORE, SESSION_COOKIE
from webui.httpio.read_cookie import read_cookie
from webui.session.renew_session import renew_session


def find_session(app, headers, cert):
    """Purpose: Gates 3 and 4: the signed-in session for this request, bound to the presented certificate, renewing its
             ID token shortly before it expires.
    Inputs:  app — App; headers — the request headers (the __Host-webui cookie); cert — dict from
             verified_client_cert.
    Returns: a copy of the session plus 'sid': {user, fp, csrf, id_token, refresh_token, perms, exp, created, last,
             auth_at, sid}; None when there is no cookie, the id is unknown, the session is idle or too old, the
             certificate fingerprint or CN differs (the session is then deleted), or renewal failed.
    Fails:   OIDC refusals are a None return (via renew_session); OSError / ssl.SSLError from the Keycloak refresh
             propagate to handle_request (500).
    Feeds:   handler.Handler.handle_request (None → redirect to /login; else the ID token goes to agentclient and the
             session to the routes).
    Notes:   It updates 'last' (idle timer) and renews when fewer than REFRESH_BEFORE (60 s) remain on the ID token, so
             role changes in Keycloak apply within one token lifetime.
    """
    sid = read_cookie(headers, SESSION_COOKIE)
    if not sid:
        return None
    now = time.time()
    with app.lock:
        s = app.sessions.get(sid)
        if not s:
            return None
        if (now - s["last"] > app.idle or now - s["created"] > app.max_age
                or not hmac.compare_digest(s["fp"], cert["fp"]) or s["user"] != cert["cn"]):
            del app.sessions[sid]
            return None
        s["last"] = now
        sess = dict(s, sid=sid)
    if sess["exp"] - now < REFRESH_BEFORE and not renew_session(app, sess):
        return None
    return sess
