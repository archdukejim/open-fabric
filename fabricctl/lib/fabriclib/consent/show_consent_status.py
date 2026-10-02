from fabriclib.consent.consent_status import consent_status


def show_consent_status(config_dir):
    """Purpose: print what fabric may change on this host, for `fabricctl status` (design host-consent.md §3).
    Inputs:  config_dir — the install's config folder.
    Returns: None; one line per group, a declined group with what it leaves unmanaged; one line saying setup
             will ask when the install predates consent.
    Fails:   yaml.YAMLError / OSError from consent_status.
    Feeds:   cli (`fabricctl status`)."""
    rows = consent_status(config_dir)
    print("\nhost changes:")
    if not rows:
        print("  not asked yet: the next `sudo fabricctl setup` asks before changing the host")
        return
    for r in rows:
        when = f" ({r['when']}, {r['by']})" if r["when"] else ""
        print(f"  {r['group']:<10} {r['state']}{when}")
        if r["relaxation"]:
            print(f"             relaxed: {r['relaxation']}")
