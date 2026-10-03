import os

from fabriclib.keycloak.admin_client import Admin


def keycloak_admin(v, s):
    """Purpose: A Keycloak admin REST client and the realm fabric uses.
    Inputs:  v — fabric vars: deploy_base_dir (root CA), ip_keycloak, hostname_keycloak, webui_realm (else
             domain); s — fabric's secrets (dict): keycloak_admin_user, keycloak_admin_password.
    Returns: (Admin (keycloak/admin_client) over a TLSClient to <ip_keycloak>:8443 verified against the fabric
             root CA for hostname_keycloak, realm name). No request is made yet (login on first call).
    Fails:   KeyError on missing vars or secrets; ImportError if webui.tlsclient cannot be imported.
    Feeds:   create_person, reset_sign_in, require_password_change, user_has_role.
    """
    from webui.tlsclient import TLSClient     # fabric/lib/webui
    ca = os.path.join(v["deploy_base_dir"], "stepca", "data", "certs", "root_ca.crt")
    kc = Admin(TLSClient(v["ip_keycloak"], 8443, v["hostname_keycloak"], ca),
              s["keycloak_admin_user"], s["keycloak_admin_password"])
    return kc, v.get("webui_realm") or v["domain"]
