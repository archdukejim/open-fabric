from fabriclib.dns.normalize_acl_policies import normalize_acl_policies
from fabriclib.dns.normalize_tsig_keys import normalize_tsig_keys
from fabriclib.secrets.random_secret import random_secret


def merge_tsig_keys(custom_vars, secrets):
    """Purpose: TSIG keys and BIND ACL policies from the vars file, checked; each key's secret in fabric's secrets.
    Inputs:  custom_vars — the admin's vars (tsig_keys, tsig_secrets, bind_acl_policies, bind_acls, domain), changed
             in place; secrets — dict with tsig_secrets, changed in place.
    Returns: (tsig_keys — the normalized list, changed — True if a secret was added or replaced).
    Fails:   ValidationError from normalize_tsig_keys / normalize_acl_policies.
    Feeds:   apply_deployment.
    Notes:   an embedded `secret` (an existing key whose RFC2136 clients must keep working) moves into the secrets and
             always wins; otherwise one is generated once and kept. A key's `acls` puts it in those BIND ACLs (the
             same entries `fabricctl tsig --acl` writes)."""
    tsig_keys, embedded = normalize_tsig_keys(custom_vars.get("tsig_keys", []), custom_vars.get("domain", ""),
                                              custom_vars.pop("tsig_secrets", None))
    custom_vars["tsig_keys"] = tsig_keys
    custom_vars["bind_acl_policies"] = normalize_acl_policies(custom_vars.get("bind_acl_policies"),
                                                              custom_vars.get("domain", ""))
    acl_map = custom_vars.get("bind_acls") or {}
    for key in tsig_keys:
        member = f'key "{key["name"]}"'
        for acl in key.get("acls") or []:
            entries = acl_map.setdefault(acl, []) or []
            if member not in entries:
                entries.append(member)
            acl_map[acl] = entries
    if acl_map:
        custom_vars["bind_acls"] = acl_map
    changed = False
    for kname, secret in embedded.items():
        if secrets["tsig_secrets"].get(kname) != secret:
            secrets["tsig_secrets"][kname] = secret
            changed = True
    for key in tsig_keys:
        kname = key.get("name")
        if kname and kname not in secrets["tsig_secrets"]:
            secrets["tsig_secrets"][kname] = random_secret(32)
            changed = True
    return tsig_keys, changed
