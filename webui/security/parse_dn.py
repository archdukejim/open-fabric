def parse_dn(dn):
    """Purpose: Split an RFC 2253 distinguished name (as nginx's $ssl_client_s_dn / _i_dn gives it) into (attribute,
             value) pairs, honouring backslash escapes.
    Inputs:  dn — str, e.g. 'CN=jim,O=Fabric'; may be empty.
    Returns: list of (ATTRIBUTE upper-cased, value) tuples, whitespace stripped, in the order given; an empty dn
             gives [('', '')].
    Fails:   never.
    Feeds:   app_state.App (issuer_dn of the Step-CA intermediate) and verified_client_cert (issuer and subject of the
             presented certificate).
    Notes:   An escaped character is kept literally (so an escaped comma does not split); hex escapes (such as an
             escaped 2C) are not decoded and multi-valued RDNs ('+') are not split. Both sides are parsed the same
             way, so the issuer comparison still works.
    """
    parts, cur, esc = [], "", False
    for ch in dn:
        if esc:
            cur += ch
            esc = False
        elif ch == "\\":
            esc = True
        elif ch == ",":
            parts.append(cur)
            cur = ""
        else:
            cur += ch
    parts.append(cur)
    out = []
    for p in parts:
        k, _, v = p.partition("=")
        out.append((k.strip().upper(), v.strip()))
    return out
