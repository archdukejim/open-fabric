def suggested_ad_domain(domain):
    """Purpose: the AD domain setup suggests (D87, manual 1.6.3.3): a protected sibling at the top of the
             organisation's name, so the Windows domain stays apart from the sites' names — `ad.` plus fabric's
             domain without its first label (lan.j-j.family -> ad.j-j.family).
    Inputs:  domain — str, fabric's domain on the first node (the root site).
    Returns: str, the suggestion; "" when the domain has no parent to use (two labels or fewer, e.g. example.org:
             `ad.org` would be someone else's) — setup then asks with no suggestion.
    Fails:   never.
    Feeds:   setup/ask_windows_domain, deploy/check_samba_settings (its messages)."""
    labels = str(domain or "").lower().strip(".").split(".")
    return "ad." + ".".join(labels[1:]) if len(labels) >= 3 else ""
