import base64
import binascii
import re

from fabriclib.common.errors import ValidationError

ALGORITHMS = ("hmac-sha256", "hmac-sha512", "hmac-sha384", "hmac-sha224", "hmac-sha1", "hmac-md5")
NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,62}$")
LABEL_RE = re.compile(r"^(?!-)[A-Za-z0-9*_-]{1,63}(?<!-)(\.(?!-)[A-Za-z0-9_-]{1,63}(?<!-))*$")
RTYPE_RE = re.compile(r"^[A-Z0-9]{1,10}$")
ACL_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,62}$")


def normalize_tsig_keys(keys, domain, secrets=None):
    """Validate tsig_keys and fill defaults. Returns (keys, embedded_secrets).

    Entry: {name, algorithm=hmac-sha256, domain=<domain>, record_types=[TXT],
    records=[host, ...] (optional: only _acme-challenge.<host>.<domain>),
    primary (optional), out (optional rfc2136.ini path), acls (optional:
    BIND ACLs to put the key in),
    secret (optional: an existing key's base64 secret, e.g. from another
    DNS server whose clients must keep working)}.

    `secret` values are taken out of the entries (secrets belong in
    fabric-secrets.yml, never in vars) and returned as {name: secret},
    together with any in a separate `secrets` mapping {name: secret}."""
    embedded = {}
    for name, secret in (secrets or {}).items():
        embedded[str(name)] = str(secret)
    out, seen = [], set()
    for raw in keys or []:
        if not isinstance(raw, dict) or not raw.get("name"):
            raise ValidationError(f"tsig_keys entry needs a name: {raw!r}")
        key = dict(raw)
        name = str(key["name"])
        if not NAME_RE.match(name) or name in seen:
            raise ValidationError(f"invalid or duplicate TSIG key name: {name!r}")
        seen.add(name)
        key["algorithm"] = str(key.get("algorithm") or "hmac-sha256").lower()
        if key["algorithm"] not in ALGORITHMS:
            raise ValidationError(f"TSIG key {name}: algorithm must be one of {', '.join(ALGORITHMS)}")
        dom = str(key.get("domain") or domain).replace("{{ domain }}", domain).replace("{{domain}}", domain)
        if not LABEL_RE.match(dom.rstrip(".")):
            raise ValidationError(f"TSIG key {name}: invalid domain {dom!r}")
        key["domain"] = dom.rstrip(".")
        key["record_types"] = [str(t).upper() for t in (key.get("record_types") or ["TXT"])]
        if not all(RTYPE_RE.match(t) for t in key["record_types"]):
            raise ValidationError(f"TSIG key {name}: invalid record_types {key['record_types']!r}")
        if key.get("records"):
            key["records"] = [str(r).rstrip(".") for r in key["records"]]
            bad = [r for r in key["records"] if not LABEL_RE.match(r)]
            if bad:
                raise ValidationError(f"TSIG key {name}: invalid record names {bad!r}")
        if key.get("acls"):
            key["acls"] = [str(a) for a in key["acls"]]
            bad = [a for a in key["acls"] if not ACL_RE.match(a) or a in ("any", "none", "localhost", "localnets",
                                                                             "tsig-updaters")]
            if bad:
                raise ValidationError(f"TSIG key {name}: invalid ACL names {bad!r}")
        if "secret" in key:
            embedded[name] = str(key.pop("secret"))
        out.append(key)
    for name, secret in embedded.items():
        try:
            if not base64.b64decode(secret, validate=True):
                raise ValueError
        except (binascii.Error, ValueError):
            raise ValidationError(f"TSIG key {name}: secret is not valid base64") from None
    return out, embedded
