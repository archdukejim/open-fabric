from fabriclib.common.load_vars import load_vars


def list_tsig_keys():
    """TSIG keys from vars.yaml with what each may update (no secrets)."""
    data = load_vars()
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
                    "ini": k.get("out") or f"/opt/{k.get('name')}/rfc2136.ini"})
    return out
