from webui.constants import PERM_PREFIX


def token_perms(claims):
    """Purpose: List the fabric permissions in a verified ID token: every role in the 'roles' claim that starts with
             'fabric:', with the prefix removed.
    Inputs:  claims — dict of verified ID token claims; reads claims['roles'] (a list; non-str entries are ignored;
             missing or empty means none).
    Returns: sorted list of unique permission names, e.g. ['dns:read', 'dns:write']; [] if there are none.
    Fails:   never for a list or missing 'roles'; TypeError if 'roles' is a truthy non-iterable value.
    Feeds:   session/finish_login (none → 403) and session/renew_session (none → session ends); stored as
             sess['perms'] and shown to pages through session/page_context → views' can().
    """
    return sorted({r[len(PERM_PREFIX):] for r in claims.get("roles") or []
                   if isinstance(r, str) and r.startswith(PERM_PREFIX)})
