from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.dns.replace_tsig_secret import replace_tsig_secret
from fabriclib.dns.rfc2136_settings import rfc2136_settings


def rotate_tsig_key(actor, name, source="web"):
    """Purpose: Give a TSIG key a newly generated secret and return what its clients need. Run apply afterwards; the old
             secret is then refused.
    Inputs:  actor — str, who asks (audit).
             name — str key name.
             source — default "web". Reads vars.yaml.
    Returns: (secret, rfc2136_ini_text).
    Fails:   ValidationError "no TSIG key named …" (from replace_tsig_secret, or if the key vanished meanwhile); errors
             from save_secrets; OSError or yaml.YAMLError from load_vars.
    Feeds:   agent route POST /v1/tsig/<name>/rotate (fabric-agent, fabricctl/lib/agent/, called by the web UI);
             tests/pki/run.py.
    """
    secret = replace_tsig_secret(actor, name, None, source=source)
    v = load_vars()
    key = next((k for k in v.get("tsig_keys") or [] if k.get("name") == name), None)
    if key is None:
        raise ValidationError(f"no TSIG key named {name!r}")
    return secret, rfc2136_settings(v, key, secret)
