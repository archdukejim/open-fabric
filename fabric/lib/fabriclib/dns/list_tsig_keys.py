import re

from fabriclib.common.load_vars import load_vars


def list_tsig_keys():
    """TSIG keys from vars.yaml with what each may update and the ACLs it is
    in (no secrets)."""
    data = load_vars()
    acls = data.get("bind_acls") or {}
    out = []
    for k in data.get("tsig_keys") or []:
        dom = k.get("domain") or data.get("domain")
        if k.get("records"):
            scope = ", ".join(f"_acme-challenge.{r}.{dom}" for r in k["records"])
        elif k.get("primary"):
            scope = f"_acme-challenge (zone {dom})"
        else:
            scope = f"any name in {dom}"
        out.append({"name": k.get("name"), "algorithm": k.get("algorithm", "hmac-sha256"),
                    "types": " ".join(k.get("record_types") or ["TXT"]), "scope": scope,
                    "ini": k.get("out") or f"/opt/{k.get('name')}/rfc2136.ini",
                    "acls": sorted(a for a, entries in acls.items()
                                   if any(re.fullmatch(rf'key\s+"?{re.escape(k.get("name", ""))}"?', str(e).strip())
                                          for e in entries or []))})
    return out
