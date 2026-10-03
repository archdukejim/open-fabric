from http import cookies


def read_cookie(headers, name):
    """Purpose: Read one cookie from the request.
    Inputs:  headers — the request headers (Cookie); name — str cookie name.
    Returns: the cookie value str, or None when it is absent or the Cookie header does not parse.
    Fails:   never.
    Feeds:   session/find_session (__Host-webui) and session/finish_login (__Host-webui-login).
    """
    jar = cookies.SimpleCookie()
    try:
        jar.load(headers.get("Cookie", ""))
    except cookies.CookieError:
        return None
    return jar[name].value if name in jar else None
