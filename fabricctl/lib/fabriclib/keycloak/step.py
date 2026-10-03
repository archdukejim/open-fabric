def step(msg):
    """Purpose: print one progress line of the Keycloak configuration ("  - <msg>").
    Inputs:  msg — str.
    Returns: None.
    Fails:   never.
    Feeds:   configure_keycloak and its ensure_* steps."""
    print(f"  - {msg}")
