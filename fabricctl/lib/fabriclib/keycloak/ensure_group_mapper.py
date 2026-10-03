from fabriclib.keycloak.quote import q
from fabriclib.keycloak.step import step

LDAP_MAPPER = "org.keycloak.storage.ldap.mappers.LDAPStorageMapper"


def ensure_group_mapper(kc, realm, ldap_id, v):
    """Purpose: create or update the LDAP group mapper (groupOfNames under ou=groups, LDAP_ONLY) and sync the
             directory's groups into Keycloak.
    Inputs:  kc — Admin; realm — realm name; ldap_id — federation id from ensure_ldap_federation; v — vars
             (ldap_base_dn).
    Returns: None.
    Fails:   SystemExit from Admin.call (including a failed sync); KeyError if ldap_base_dn is missing; StopIteration if
             a created mapper cannot be found again.
    Feeds:   configure_keycloak (the synced groups are what grant_role_to_group looks up)."""
    config = {
        "groups.dn": [f"ou=groups,{v['ldap_base_dn']}"],
        "group.name.ldap.attribute": ["cn"],
        "group.object.classes": ["groupOfNames"],
        "preserve.group.inheritance": ["false"],
        "membership.ldap.attribute": ["member"],
        "membership.attribute.type": ["DN"],
        "membership.user.ldap.attribute": ["uid"],
        "memberof.ldap.attribute": ["memberOf"],
        "mode": ["LDAP_ONLY"],
        "user.roles.retrieve.strategy": ["LOAD_GROUPS_BY_MEMBER_ATTRIBUTE"],
        "drop.non.existing.groups.during.sync": ["false"],
    }
    path = f"/{q(realm)}/components?parent={ldap_id}&type={q(LDAP_MAPPER)}"
    _, mappers = kc.call("GET", path)
    mapper = next((m for m in mappers if m.get("providerId") == "group-ldap-mapper"), None)
    if mapper is None:
        kc.call("POST", f"/{q(realm)}/components", {
            "name": "LDAP Groups", "providerId": "group-ldap-mapper", "providerType": LDAP_MAPPER,
            "parentId": ldap_id, "config": config})
        _, mappers = kc.call("GET", path)
        mapper = next(m for m in mappers if m.get("providerId") == "group-ldap-mapper")
        step("created LDAP group mapper")
    else:
        mapper["config"] = {**mapper.get("config", {}), **config}
        kc.call("PUT", f"/{q(realm)}/components/{mapper['id']}", mapper)
    kc.call("POST", f"/{q(realm)}/user-storage/{ldap_id}/mappers/{mapper['id']}/sync?direction=fedToKeycloak")
    step("synced LDAP groups into Keycloak")
