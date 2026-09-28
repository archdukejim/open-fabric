from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.dns.replace_tsig_secret import replace_tsig_secret
from fabriclib.dns.rfc2136_settings import rfc2136_settings


def rotate_tsig_key(actor, name, source="web"):
    """Give a TSIG key a newly generated secret and return (secret,
    rfc2136_ini_text) for its clients. Run apply afterwards; the old secret
    is then refused."""
    secret = replace_tsig_secret(actor, name, None, source=source)
    v = load_vars()
    key = next((k for k in v.get("tsig_keys") or [] if k.get("name") == name), None)
    if key is None:
        raise ValidationError(f"no TSIG key named {name!r}")
    return secret, rfc2136_settings(v, key, secret)
