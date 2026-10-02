import urllib.parse


def quote_segment(s):
    """Purpose: URL-quote one path segment with nothing kept safe ("/" becomes %2F), so a name cannot change the route.
    Inputs:  s — any value; converted with str().
    Returns: the quoted str.
    Fails:   never.
    Feeds:   every function here that puts a zone, key, slot, device, role, MAC, group, client or uid in the path.
    """
    return urllib.parse.quote(str(s), safe="")
