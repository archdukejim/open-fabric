from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.common.save_vars import save_vars
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit
from fabriclib.dns.add_acl_entries import NAME_RE, RESERVED
from fabriclib.dns.normalize_acl_policies import normalize_acl_policies


def set_acl_policy(actor, acl, policy, source="cli"):
    """Purpose: Give ACL `acl` an update policy that every TSIG key in it inherits as BIND update-policy grants, or
             remove it. The ACL is created (empty) if missing. Run apply afterwards.
    Inputs:  actor — str, who asks (audit).
             acl — str matching NAME_RE, not reserved.
             policy — dict (records | any_name, record_types, domain; see normalize_acl_policies), or None to remove it.
             source — "cli" (default) or "web". Reads/writes vars.yaml under vars_lock.
    Returns: the stored policy dict, or None when removed.
    Fails:   ValidationError "invalid ACL name …", "ACL … has no update policy", or one from normalize_acl_policies;
             OSError or yaml.YAMLError from vars_lock / load_vars / save_vars / write_audit.
    Feeds:   run_acl_command (`fabricctl acl policy`).
    """
    if not NAME_RE.match(acl) or acl in RESERVED:
        raise ValidationError(f"invalid ACL name {acl!r}")
    with vars_lock():
        data = load_vars()
        policies = dict(data.get("bind_acl_policies") or {})
        if policy is None:
            if acl not in policies:
                raise ValidationError(f"ACL {acl!r} has no update policy")
            del policies[acl]
            stored = None
        else:
            stored = normalize_acl_policies({acl: policy}, data.get("domain", ""))[acl]
            policies[acl] = stored
            acls = dict(data.get("bind_acls") or {})
            acls.setdefault(acl, [])
            data["bind_acls"] = acls
        data["bind_acl_policies"] = policies
        save_vars(data)
    write_audit(actor, "ACL_POLICY", f"acl={acl} policy={stored}", source)
    return stored
