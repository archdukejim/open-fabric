from fabriclib.pki.cert_warnings import cert_warnings


def show_cert_warnings(vars_):
    """Purpose: print what is wrong or coming with fabric's certificates, for `fabricctl status` (manual 2.1.5.4).
    Inputs:  vars_ — the host's vars.
    Returns: None; a heading and one line per warning, or one line saying all is well.
    Fails:   never.
    Feeds:   cli (`fabricctl status`)."""
    rows = cert_warnings(vars_)
    print("\ncertificates:")
    if not rows:
        print("  every certificate current; renewal working")
    for r in rows:
        print(f"  {'FAIL' if r['level'] == 'fail' else 'warn'}: {r['what']}")
