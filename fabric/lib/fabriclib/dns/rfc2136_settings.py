def rfc2136_settings(v, key, secret):
    """The rfc2136.ini a certbot-style client (e.g. nginx-proxy-manager's
    DNS challenge) needs for one TSIG key: server, port, key name, secret,
    algorithm, zone."""
    return (f"# RFC2136 credentials for TSIG key: {key['name']}\n"
            f"dns_rfc2136_server = {v.get('host_ip')}\n"
            f"dns_rfc2136_port = {v.get('bind_dns_port', 53)}\n"
            f"dns_rfc2136_name = {key['name']}\n"
            f"dns_rfc2136_secret = {secret}\n"
            f"dns_rfc2136_algorithm = {key.get('algorithm', 'hmac-sha256').upper()}\n"
            f"dns_rfc2136_base_domain = {key.get('domain', v.get('domain'))}\n")
