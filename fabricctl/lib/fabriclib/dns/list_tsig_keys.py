import re

from fabriclib.common.load_vars import load_vars


def _names(records, dom):
    """Purpose: The _acme-challenge names a list of hosts may update, for display.
    Inputs:  records — list of host labels; dom — str zone name.
    Returns: str "_acme-challenge.<host>.<dom>, …".
    Fails:   never.
    Feeds:   list_tsig_keys.
    """
    return ", ".join(f"_acme-challenge.{r}.{dom}" for r in records)


def list_tsig_keys():
    """Purpose: The TSIG keys in vars.yaml with their effective update rights (their own grants plus those inherited
             from ACL policies) and the ACLs that hold them; never secrets. Rights are deny-by-default.
    Inputs:  none. Reads vars.yaml (tsig_keys, bind_acls, bind_acl_policies, domain).
    Returns: [{"name", "algorithm", "types" (space-joined), "scope" (text; "no update rights" if none), "ini"
             (rfc2136.ini path), "acls" (sorted ACL names)}].
    Fails:   OSError or yaml.YAMLError from load_vars; KeyError if a stored ACL policy lacks domain or record_types
             (normalized policies always have them).
    Feeds:   agent route GET /v1/tsig (fabricctl/lib/agent/server.py, called by webui/server.py); run_tsig_command
             (list, update, after-apply output); tests/pki/run.py.
    Notes:   ACL membership counts only positive `key "<name>"` entries (a `!key` exclusion is not membership). The
             default "ini" is hard-coded as /opt/<name>/rfc2136.ini, while apply writes it under the deploy base.
    """
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
