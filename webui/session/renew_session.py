from webui.oidc import OIDCError
from webui.security.token_perms import token_perms


def renew_session(app, sess):
    """Purpose: Replace a session's ID token with a fresh one from Keycloak, picking up the person's current roles; end
             the session if Keycloak refuses.
    Inputs:  app — App; sess — dict from find_session (uses sid, refresh_token, user); updated in place on success.
    Returns: True if renewed (stored session and sess get id_token, refresh_token, perms, exp); False if Keycloak
             refused (OIDCError), the new token has no fabric permission, or the username changed — these remove the
             stored session — or the session vanished meanwhile.
    Fails:   OSError / ssl.SSLError from the Keycloak call propagate (500 in handle_request).
    Feeds:   find_session.
    Notes:   auth_at is not changed: a refresh is not a new sign-in, so the vault step-up still needs one.
    """
    try:
        claims, id_token, refresh_token = app.oidc.refresh(sess["refresh_token"])
    except OIDCError:
        with app.lock:
            app.sessions.pop(sess["sid"], None)
        return False
    perms = token_perms(claims)
    with app.lock:
        if not perms or claims.get("preferred_username") != sess["user"]:
            app.sessions.pop(sess["sid"], None)
            return False
        stored = app.sessions.get(sess["sid"])
        if stored is None:
            return False
        stored.update(id_token=id_token, refresh_token=refresh_token, perms=perms,
                      exp=float(claims.get("exp") or 0))
    sess.update(id_token=id_token, refresh_token=refresh_token, perms=perms, exp=float(claims.get("exp") or 0))
    return True
