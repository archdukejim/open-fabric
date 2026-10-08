def suggested_ad_domain(domain):
    """Purpose: the AD domain setup suggests (D87, manual 1.6.3.3): a protected sibling at the top of the
             organisation's name, so the Windows domain stays apart from the sites' names — `ad.` plus fabric's
             domain without its first label (lan.j-j.family -> ad.j-j.family).
    Inputs:  domain — str, fabric's domain on the first node (the root site).
    Returns: str, the suggestion; for a two-label domain, which has no parent of its own to use (`ad.org` would be
             someone else's), a sub-domain instead: `ad.` plus the domain (home.arpa -> ad.home.arpa; owner
             2026-10-08: setup always offers one to take with Enter); "" for one label or none.
    Fails:   never.
    Feeds:   setup/ask_windows_domain, deploy/check_samba_settings (its messages)."""
    labels = str(domain or "").lower().strip(".").split(".")
    if len(labels) >= 3:
        return "ad." + ".".join(labels[1:])
    return "ad." + ".".join(labels) if len(labels) == 2 and all(labels) else ""
