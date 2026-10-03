from fabriclib.keycloak.quote import q
from fabriclib.keycloak.step import step

USER_STORAGE = "org.keycloak.storage.UserStorageProvider"


def ensure_ldap_federation(kc, realm, realm_id, v, s, writable=True):
    """Purpose: create or update the realm's LDAP user federation to 389-DS ("389-DS": ldaps on port 3636, users under
             ou=users,ou=accounts, bound as this install's cn=keycloak_admin (its own site part), writable, imports
             users).
    Inputs:  kc — Admin; realm — realm name; realm_id — parent id from ensure_realm; v — vars (ldap_base_dn,
             ldap_local_dn, hostname_ldap); s — secrets (ldap_keycloak_password); writable — False at a federated
             site (READ_ONLY: people are changed at the root).
    Returns: str, the federation component id. An existing ldap provider is updated in place (fabric's settings win,
             other settings kept).
    Fails:   SystemExit from Admin.call; KeyError if a needed var or secret is missing; StopIteration if a created
             provider cannot be found again.
    Feeds:   configure_keycloak (the id is passed to ensure_group_mapper)."""
    base = v["ldap_base_dn"]
    config = {
        "enabled": ["true"],
        "vendor": ["rhds"],
        # people are written only where the organisation is (a standalone install, the root site): at a federated
        # site the directory holds a read-only copy, so Keycloak does not offer changes it cannot make (M5)
        "editMode": ["WRITABLE" if writable else "READ_ONLY"],
        "syncRegistrations": ["true" if writable else "false"],
        "importEnabled": ["true"],
        "usernameLDAPAttribute": ["uid"],
        "rdnLDAPAttribute": ["uid"],
        "uuidLDAPAttribute": ["entryUUID"],
        "userObjectClasses": ["inetOrgPerson, organizationalPerson"],
        "connectionUrl": [f"ldaps://{v['hostname_ldap']}:3636"],
        "usersDn": [f"ou=users,ou=accounts,{base}"],
        "authType": ["simple"],
        "bindDn": [f"cn=keycloak_admin,ou=admins,{v['ldap_local_dn']}"],
        "bindCredential": [s["ldap_keycloak_password"]],
        "searchScope": ["1"],
        "useTruststoreSpi": ["always"],
        "startTls": ["false"],
        "connectionPooling": ["true"],
        "pagination": ["true"],
        "usePasswordModifyExtendedOp": ["true"],
        "trustEmail": ["true"],
        "batchSizeForSync": ["1000"],
    }
    _, comps = kc.call("GET", f"/{q(realm)}/components?type={q(USER_STORAGE)}")
    ldap = next((c for c in comps if c.get("providerId") == "ldap"), None)
    if ldap is None:
        kc.call("POST", f"/{q(realm)}/components", {
            "name": "389-DS", "providerId": "ldap", "providerType": USER_STORAGE,
            "parentId": realm_id, "config": config})
        _, comps = kc.call("GET", f"/{q(realm)}/components?type={q(USER_STORAGE)}")
        ldap = next(c for c in comps if c.get("providerId") == "ldap")
        step("created LDAP federation (389-DS)")
    else:
        ldap["name"] = "389-DS"
        ldap["config"] = {**ldap.get("config", {}), **config}
        kc.call("PUT", f"/{q(realm)}/components/{ldap['id']}", ldap)
        step(f"updated LDAP federation {ldap['id']} -> {config['connectionUrl'][0]}")
    return ldap["id"]
