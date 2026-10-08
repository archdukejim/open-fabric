def sso_spns(v):
    """Purpose: the SPNs of the site's Kerberos sign-in account (manual 2.3.6.2.6.2): Keycloak's name, and the host's
             name, which sso.<domain> is a CNAME of (Windows browsers ask for the ticket of the name a CNAME points to).
    Inputs:  v — rendered vars: install_keycloak, signin_kerberos, hostname_keycloak, hostname, domain, ad_dc_type.
    Returns: list of str ("HTTP/<name>"), [] when there is no Kerberos sign-in here: Keycloak off, signin_kerberos
             false, or a read-only DC (it cannot make the account).
    Fails:   KeyError for a missing var.
    Feeds:   converge_domain."""
    if not v.get("install_keycloak") or not v.get("signin_kerberos", True) or v.get("ad_dc_type") == "rodc":
        return []
    names = [v["hostname_keycloak"], f"{v['hostname']}.{v['domain']}".lower()]
    return [f"HTTP/{n}" for n in dict.fromkeys(names)]
