RECORD_TYPES = ("A", "AAAA", "CNAME", "MX", "TXT", "SRV")


def upgrade_vars(data, pinned):
    """Adjust an existing install's rendered vars before they are re-rendered
    by a newer fabric:

    - image_* keys are dropped unless `pinned` sets them, so an upgrade picks
      up the new release's images instead of freezing the old ones.
    - a zone keyed by the literal domain (pre-dynamic_zone_var installs) is
      merged into dynamic_zone_var; both would render to db.<domain>.
    Returns the list of changes made, for the log."""
    changes = []
    for key in [k for k in data if k.startswith("image_") and k not in pinned]:
        del data[key]
        changes.append(f"{key}: use this release's default")

    dns, domain = data.get("dns") or {}, data.get("domain")
    if domain and domain in dns and "dynamic_zone_var" in dns:
        legacy, dyn = dns.pop(domain) or {}, dns["dynamic_zone_var"] or {}
        for rtype in RECORD_TYPES:
            merged = list(dyn.get(rtype) or [])
            merged += [r for r in legacy.get(rtype) or [] if r not in merged]
            if merged:
                dyn[rtype] = merged
        if "zone_authority" in legacy:
            dyn["zone_authority"] = legacy["zone_authority"]
        dns["dynamic_zone_var"] = dyn
        changes.append(f"dns: merged legacy zone key '{domain}' into dynamic_zone_var")
    return changes
