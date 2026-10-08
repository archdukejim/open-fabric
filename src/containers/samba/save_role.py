import ldb
from samba.dsdb import GTYPE_DISTRIBUTION_GLOBAL_GROUP

from paths import organisation_dn, site_dn


def save_role(samdb, lp, site, name, description, permissions, vlan, priority, new, organisation=False):
    """Purpose: a device role in AD (manual 1.6.3.5): what it grants its devices, an optional VLAN, a priority (the
             lower number wins). A role is a distribution group (never in anyone's sign-in token) with fabric's
             `fabricRole` class, named `role-<name>`; a new one goes in this site's OU=device-roles, or with
             `organisation` (fabric's defaults, at the root) in OU=organisation's. Fields are checked by fabric first.
    Inputs:  samdb — SamDB (as the site's agent); lp — LoadParm (unused); site — str; name — the role's name;
             description — str; permissions — list; vlan — int or None; priority — int; new — bool: add (else
             replace the role wherever it lives); organisation — bool (add only).
    Returns: {"name"}.
    Fails:   ldb.LdbError ERR_ENTRY_ALREADY_EXISTS (add), ERR_NO_SUCH_OBJECT (replace), ERR_INSUFFICIENT_ACCESS_RIGHTS
             (a role of another site, or the organisation's from a site).
    Feeds:   directory_ops (ops "add_role", "update_role"); fabric's default roles."""
    values = {"description": description, "fabricPermission": list(permissions),
              "fabricVlan": str(vlan) if vlan else "", "fabricPriority": str(priority)}
    if new:
        where = f"OU=device-roles,{organisation_dn(samdb)}" if organisation \
            else f"OU=device-roles,{site_dn(samdb, site)}"
        samdb.newgroup(f"role-{name}", groupou=where.replace(f",{samdb.domain_dn()}", ""),
                       grouptype=GTYPE_DISTRIBUTION_GLOBAL_GROUP)
        dn = f"CN=role-{name},{where}"
        samdb.rename(dn, f"CN={name},{where}")
        dn = f"CN={name},{where}"
        msg = ldb.Message(ldb.Dn(samdb, dn))
        msg["objectClass"] = ldb.MessageElement(["fabricRole"], ldb.FLAG_MOD_ADD, "objectClass")
        samdb.modify(msg)
    else:
        found = samdb.search(base=f"OU=sites,{samdb.domain_dn()}", scope=ldb.SCOPE_SUBTREE,
                             expression=f"(&(objectClass=fabricRole)(cn={ldb.binary_encode(name)}))", attrs=["dn"])
        if not found:
            raise ldb.LdbError(ldb.ERR_NO_SUCH_OBJECT, f"no role {name}")
        dn = str(found[0].dn)
    msg = ldb.Message(ldb.Dn(samdb, dn))
    for k, val in values.items():
        msg[k] = ldb.MessageElement(val if isinstance(val, list) else ([val] if val else []), ldb.FLAG_MOD_REPLACE, k)
    samdb.modify(msg)
    return {"name": name}
