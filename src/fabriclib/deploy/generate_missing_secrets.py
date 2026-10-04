from fabriclib.secrets.random_password import random_password
from fabriclib.secrets.random_secret import random_secret

BASE64 = {"ca_password": 32, "rndc_secret": 32, "ldap_admin_password": 24, "ldap_keycloak_password": 24,
          "keycloak_admin_password": 24, "keycloak_db_password": 32,
          "kea_ddns_secret": 32}                     # HMAC-SHA256 TSIG key for Kea's DDNS
# alphanumeric: safe inside LDIF and JSON without quoting
ALNUM = ("ldap_super_admin_password", "ldap_group_admin_password", "ldap_user_creator_password",
         "ldap_user_modifier_password", "ldap_device_admin_password", "ldap_radius_password",
         "webui_oidc_secret", "openbao_oidc_secret",
         "adguard_admin_password", "adguard_oidc_secret", "adguard_cookie_secret")


def generate_missing_secrets(secrets):
    """Purpose: create each of fabric's own secrets that does not exist yet, once (existing ones are never replaced).
    Inputs:  secrets — dict, changed in place.
    Returns: True if anything was added.
    Fails:   never.
    Feeds:   apply_deployment (before the vars are rendered: templates read the secrets)."""
    changed = False
    for name, nbytes in BASE64.items():
        if name not in secrets:
            secrets[name] = random_secret(nbytes)
            changed = True
    if "keycloak_admin_user" not in secrets:
        secrets["keycloak_admin_user"] = "admin"
        changed = True
    for name in ALNUM:
        if name not in secrets:
            secrets[name] = random_secret(alnum=True)
            changed = True
    # the Windows domain's Administrator (manual 1.6.3.7): long and of every class, so any allowed policy accepts it
    if "ad_admin_password" not in secrets:
        secrets["ad_admin_password"] = random_password()
        changed = True
    if "tsig_secrets" not in secrets:
        secrets["tsig_secrets"] = {}
        changed = True
    return changed
