import re

from fabriclib.common.load_vars import load_vars


def _names(records, dom):
    return ", ".join(f"_acme-challenge.{r}.{dom}" for r in records)


def list_tsig_keys():
    """TSIG keys from vars.yaml with their effective update rights — their
    own grants plus those inherited from ACL policies — and their ACLs (no
    secrets). Rights are deny-by-default."""
    data = load_vars()
    acls = data.get("bind_acls") or {}
    policies = data.get("bind_acl_policies") or {}
    out = []
    for k in data.get("tsig_keys") or []:
        name, dom = k.get("name", ""), k.get("domain") or data.get("domain")
        member = sorted(a for a, entries in acls.items()
                        if any(re.fullmatch(rf'key\s+"?{re.escape(name)}"?', str(e).strip()) for e in entries or []))
        rights = []
        if k.get("records"):
            rights.append(_names(k["records"], dom))
        elif k.get("primary"):
            rights.append(f"_acme-challenge (zone {dom})")
        elif k.get("any_name"):
            rights.append(f"any name in {dom}")
        for acl in member:
            pol = policies.get(acl)
            if pol:
                what = _names(pol["records"], pol["domain"]) if pol.get("records") else f"any name in {pol['domain']}"
                rights.append(f"{what} ({' '.join(pol['record_types'])}, via ACL {acl})")
        out.append({"name": name, "algorithm": k.get("algorithm", "hmac-sha256"),
                    "types": " ".join(k.get("record_types") or ["TXT"]),
                    "scope": "; ".join(rights) or "no update rights",
                    "ini": k.get("out") or f"/opt/{name}/rfc2136.ini", "acls": member})
    return out
