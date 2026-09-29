import os


def keycloak_admin(v, s):
    """(admin client, realm) for Keycloak's admin REST API: TLS pinned to
    the fabric root CA, fabric's Keycloak admin credentials (`s`: fabric's
    secrets). The client is keycloak_bootstrap's."""
    import keycloak_bootstrap as kb          # fabric/lib
    from webui.tlsclient import TLSClient
    ca = os.path.join(v["deploy_base_dir"], "stepca", "data", "certs", "root_ca.crt")
    kc = kb.Admin(TLSClient(v["ip_keycloak"], 8443, v["hostname_keycloak"], ca),
                  s["keycloak_admin_user"], s["keycloak_admin_password"])
    return kc, v.get("webui_realm") or v["domain"]
