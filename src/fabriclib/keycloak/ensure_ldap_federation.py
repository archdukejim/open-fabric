from fabriclib.keycloak.quote import q
from fabriclib.keycloak.step import step

USER_STORAGE = "org.keycloak.storage.UserStorageProvider"
NAME = "Samba AD"


def ensure_ldap_federation(kc, realm, realm_id, v, s, writable=True):
    """Purpose: the realm's user federation to fabric's directory, Samba AD (manual 1.6.3.11, 2.11.2.16 S2.5): AD mode,
             LDAPS to the DC at the host's address (verified against fabric's CA), bound as this site's
             fabric-keycloak account; people searched under OU=sites, admitted when they are in this site's
             `<site>-users` or the organisation's admin group (D90); writable, so a password changed at sign-in lands
             in AD. fabric creates people itself (directory/create_person): Keycloak does not.
    Inputs:  kc — Admin; realm — realm name; realm_id — parent id from ensure_realm; v — vars (ad_base_dn, host_ip,
             site_name, webui_admin_group); s — secrets (ad_keycloak_password); writable — False makes it READ_ONLY.
    Returns: str, the federation component id. An existing AD provider is updated in place (fabric's settings win,
             other settings kept); a provider of another kind (389-DS's) is removed first and made anew, so Keycloak
             creates AD's own mappers (account controls, pwdLastSet) with it.
    Fails:   SystemExit from Admin.call; KeyError if a needed var or secret is missing; StopIteration if a created
             provider cannot be found again.
    Feeds:   configure_keycloak (the id is passed to ensure_group_mapper)."""
    base, site = v["ad_base_dn"], v["site_name"]
    admins = v.get("webui_admin_group") or "admins"
    admitted = (f"(|(memberOf=CN={site}-users,OU=groups,OU={site},OU=sites,{base})"
                f"(memberOf=CN={admins},OU=groups,OU=organisation,OU={site},OU=sites,{base}))")
    config = {
        "enabled": ["true"],
        "vendor": ["ad"],
        "editMode": ["WRITABLE" if writable else "READ_ONLY"],
        "syncRegistrations": ["false"],
        "importEnabled": ["true"],
        "usernameLDAPAttribute": ["sAMAccountName"],
        "rdnLDAPAttribute": ["cn"],
        "uuidLDAPAttribute": ["objectGUID"],
        "userObjectClasses": ["person, organizationalPerson, user"],
        "connectionUrl": [f"ldaps://{v['host_ip']}:636"],
        "usersDn": [f"OU=sites,{base}"],
        "searchScope": ["2"],
        "customUserSearchFilter": [admitted],
        "authType": ["simple"],
        "bindDn": [f"CN=fabric-keycloak-{site},OU=service-accounts,OU={site},OU=sites,{base}"],
        "bindCredential": [s["ad_keycloak_password"]],
        "useTruststoreSpi": ["always"],
        "startTls": ["false"],
        "connectionPooling": ["true"],
        "pagination": ["true"],
        "usePasswordModifyExtendedOp": ["false"],
        "trustEmail": ["true"],
        "batchSizeForSync": ["1000"],
    }
    path = f"/{q(realm)}/components?type={q(USER_STORAGE)}"
    ldap = next((c for c in kc.call("GET", path)[1] if c.get("providerId") == "ldap"), None)
    if ldap is not None and (ldap.get("config", {}).get("vendor") or [""])[0] != "ad":
        kc.call("DELETE", f"/{q(realm)}/components/{ldap['id']}")
        step(f"removed the LDAP federation {ldap.get('name')} (fabric's directory is Samba AD)")
        ldap = None
    if ldap is None:
        kc.call("POST", f"/{q(realm)}/components", {
            "name": NAME, "providerId": "ldap", "providerType": USER_STORAGE, "parentId": realm_id, "config": config})
        ldap = next(c for c in kc.call("GET", path)[1] if c.get("providerId") == "ldap")
        step(f"created LDAP federation ({NAME})")
    else:
        ldap["name"] = NAME
        ldap["config"] = {**ldap.get("config", {}), **config}
        kc.call("PUT", f"/{q(realm)}/components/{ldap['id']}", ldap)
        step(f"updated LDAP federation {ldap['id']} -> {config['connectionUrl'][0]}")
    return ldap["id"]
