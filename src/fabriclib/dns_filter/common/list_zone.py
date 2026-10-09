import hashlib


def list_zone(url):
    """Purpose: a list's response policy zone name (manual 1.12.2.6): `<id>.list.rpz`, <id> the first 12 hex digits
             of the SHA-256 of its URL, so reordering or renaming lists never reloads one, and the RPZ log's zone
             leads back to its list.
    Inputs:  url — the list's URL (str), as in dns_filter_lists.
    Returns: str, e.g. "3f2a9c1b7d4e.list.rpz".
    Fails:   never.
    Feeds:   dns_filter/update_lists, dns_filter/deploy_resolver, dns_filter/show_filter_status."""
    return hashlib.sha256(url.strip().encode()).hexdigest()[:12] + ".list.rpz"
