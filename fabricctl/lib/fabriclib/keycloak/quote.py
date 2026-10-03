import urllib.parse


def q(s):
    """Purpose: URL-quote one path or query component (every character outside [A-Za-z0-9_.-~] escaped, "/" too).
    Inputs:  s — any value, converted with str().
    Returns: str, the quoted text.
    Fails:   never.
    Feeds:   every Admin.call path in fabriclib/keycloak; tests/keycloak/verify.py, tests/host/reset_user.py."""
    return urllib.parse.quote(str(s), safe="")
