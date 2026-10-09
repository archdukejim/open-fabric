from fabriclib.common.console import NC, YELLOW


def ask_kerberos():
    """Purpose: whether Keycloak accepts the domain logon's Kerberos ticket before asking for a password (2.1.6.32):
             asked once at setup, no by default, saying what it does and its cost on computers outside the domain.
    Inputs:  none. Interactive.
    Returns: bool.
    Fails:   EOFError from input().
    Feeds:   setup/collect_vars."""
    print("\n  Sign-in with the domain logon (Kerberos): a computer joined to fabric's domain signs in to the web "
          "console\n  and fabric's apps without a password. A browser outside the domain may then show its own "
          "sign-in box first\n  (cancel it). It can be turned on or off later on the web console's Security page.")
    while True:
        answer = input("    Turn it on now? [y/N]: ").strip().lower()
        if answer in ("", "n", "no"):
            return False
        if answer in ("y", "yes"):
            return True
        print(f"    {YELLOW}y or n{NC}")
