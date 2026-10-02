def rfc2136_settings(v, key, secret):
    """Purpose: The rfc2136.ini text a certbot-style client (e.g. nginx-proxy-manager's DNS challenge) needs for one
             TSIG key.
    Inputs:  v — the vars dict (host_ip, bind_dns_port default 53, domain).
             key — a normalized tsig_keys entry (name, algorithm, domain).
             secret — base64 str, written as is.
    Returns: str: dns_rfc2136_server, _port, _name, _secret, _algorithm (upper case) and _base_domain lines.
    Fails:   KeyError if key has no "name".
    Feeds:   deploy/render_templates (each key's rfc2136.ini), create_zone_tsig_key, rotate_tsig_key.
    Notes:   the text holds the secret; callers must keep it private.
    """
    return (f"# RFC2136 credentials for TSIG key: {key['name']}\n"
            f"dns_rfc2136_server = {v.get('host_ip')}\n"
            f"dns_rfc2136_port = {v.get('bind_dns_port', 53)}\n"
            f"dns_rfc2136_name = {key['name']}\n"
            f"dns_rfc2136_secret = {secret}\n"
            f"dns_rfc2136_algorithm = {key.get('algorithm', 'hmac-sha256').upper()}\n"
            f"dns_rfc2136_base_domain = {key.get('domain', v.get('domain'))}\n")
