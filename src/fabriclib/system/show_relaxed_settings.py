from fabriclib.system.relaxed_settings import relaxed_settings


def show_relaxed_settings(vars_):
    """Purpose: print the security relaxations that are on, for `fabricctl status` (global Rule 10).
    Inputs:  vars_ — the host's vars.
    Returns: None; a heading and one line per relaxation, or one line saying there is none.
    Fails:   never.
    Feeds:   cli (`fabricctl status`)."""
    rows = relaxed_settings(vars_)
    print("\nrelaxed security settings:")
    if not rows:
        print("  none")
    for r in rows:
        print(f"  {r['setting']}: {r['effect']}")
