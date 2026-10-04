def cookie_header(name, value, max_age, samesite="Strict"):
    """Purpose: Build a Set-Cookie header for the web UI's host-only cookies.
    Inputs:  name — str; value — str, written as is (callers pass URL-safe tokens or ''); max_age — int seconds, 0
             deletes the cookie; samesite — 'Strict' (default) or 'Lax'.
    Returns: ('Set-Cookie', '<name>=<value>; Path=/; Secure; HttpOnly; SameSite=<samesite>; Max-Age=<max_age>').
    Fails:   never.
    Feeds:   session/start_login, session/finish_login and routes/logout, which pass it to send / redirect.
    Notes:   The __Host- cookie names require Secure, Path=/ and no Domain, so no other host can set them.
    """
    return ("Set-Cookie", f"{name}={value}; Path=/; Secure; HttpOnly; SameSite={samesite}; Max-Age={max_age}")
