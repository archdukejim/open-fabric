from fabriclib.common.errors import ValidationError
from fabriclib.dns.normalize_tsig_keys import ACL_RE, LABEL_RE, RTYPE_RE


def normalize_acl_policies(policies, domain):
    """Purpose: Validate bind_acl_policies and fill defaults. Every TSIG key in a policy's ACL may then update exactly
             _acme-challenge.<host>.<domain> for the listed hosts (or, with any_name, any name in the zone) for the
             given record types — e.g. only certbot devices holding a key in the ACL can prove a name for a certificate.
    Inputs:  policies — {acl: {records: [host, …] | any_name: true, record_types (default [TXT]), domain}} or None.
             domain — str, the fabric domain: the default zone, and what "{{ domain }}" in a policy becomes.
    Returns: {acl: {"domain", "record_types" (upper case), and "records" or "any_name": True}}.
    Fails:   ValidationError "invalid ACL name …", "ACL …: invalid domain …", "…: invalid record_types …", "…: invalid
             record names …", "…: a policy needs records (hosts) or any_name".
    Feeds:   deploy/merge_tsig_keys (apply), set_acl_policy.
    Notes:   records win over any_name when both are given.
    """
    out = {}
    for acl, raw in (policies or {}).items():
        if not ACL_RE.match(str(acl)):
            raise ValidationError(f"invalid ACL name {acl!r}")
        pol = dict(raw or {})
        dom = str(pol.get("domain") or domain).replace("{{ domain }}", domain).rstrip(".")
        if not LABEL_RE.match(dom):
            raise ValidationError(f"ACL {acl}: invalid domain {dom!r}")
        types = [str(t).upper() for t in (pol.get("record_types") or ["TXT"])]
        if not all(RTYPE_RE.match(t) for t in types):
            raise ValidationError(f"ACL {acl}: invalid record_types {types!r}")
        records = [str(r).rstrip(".") for r in (pol.get("records") or [])]
        bad = [r for r in records if not LABEL_RE.match(r)]
        if bad:
            raise ValidationError(f"ACL {acl}: invalid record names {bad!r}")
        any_name = bool(pol.get("any_name"))
        if not records and not any_name:
            raise ValidationError(f"ACL {acl}: a policy needs records (hosts) or any_name")
        norm = {"domain": dom, "record_types": types}
        if records:
            norm["records"] = records
        else:
            norm["any_name"] = True
        out[str(acl)] = norm
    return out
