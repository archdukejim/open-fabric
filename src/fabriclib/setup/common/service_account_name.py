NAMES = {"bind": "fabric-dns", "nginx": "fabric-proxy", "step": "fabric-ca",
         "keycloak": "fabric-sso", "postgres": "fabric-db", "webui": "fabric-webui", "openbao": "fabric-vault",
         "fluentbit": "fabric-logs", "kea": "fabric-dhcp", "freeradius": "fabric-radius",
         "resolver": "fabric-resolver"}


def service_account_name(key, ids):
    """Purpose: the host account name of one service_users entry (manual 1.2.9.6): fabric-* names,
             so no Ubuntu package ever claims or questions them.
    Inputs:  key — the service_users key (e.g. "bind"); ids — its entry ({uid, gid[, name]}).
    Returns: ids["name"] when set, else NAMES[key], else "fabric-<key>".
    Fails:   never.
    Feeds:   consent/plan_accounts, setup/uninstall."""
    return (ids or {}).get("name") or NAMES.get(key) or f"fabric-{key}"
