from webui.security.parse_dn import parse_dn


def verified_client_cert(headers, issuer_dn):
    """Purpose: Gates 1 and 2: the verified client certificate nginx forwarded, accepted only if it was issued directly
             by the fabric Step-CA intermediate.
    Inputs:  headers — the request headers: X-SSL-Client-Verify, X-SSL-Client-I-DN, X-SSL-Client-S-DN and
             X-SSL-Client-Fingerprint (set by nginx); issuer_dn — the intermediate's subject (App.issuer_dn).
    Returns: {'cn': str, 'fp': str} — the subject CN and certificate fingerprint; None when verification did not
             succeed, the issuer DN differs from the intermediate's (compared as a set of attributes), the subject does
             not have exactly one non-empty CN, or the fingerprint is missing.
    Fails:   never — refusal is the None return.
    Feeds:   handler.Handler.handle_request (None → 403), then start_login, finish_login and find_session.
    Notes:   The headers can be trusted only because the server listens on a unix socket that nobody but nginx can
             reach.
    """
    if headers.get("X-SSL-Client-Verify") != "SUCCESS":
        return None
    issuer = parse_dn(headers.get("X-SSL-Client-I-DN", ""))
    if sorted(issuer) != sorted(issuer_dn):
        return None
    subject = parse_dn(headers.get("X-SSL-Client-S-DN", ""))
    cns = [v for k, v in subject if k == "CN"]
    fp = headers.get("X-SSL-Client-Fingerprint", "")
    if len(cns) != 1 or not cns[0] or not fp:
        return None
    return {"cn": cns[0], "fp": fp}
