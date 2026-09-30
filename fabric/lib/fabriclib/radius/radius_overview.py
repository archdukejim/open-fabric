from fabriclib.radius.list_auth_log import list_auth_log


def radius_overview(v, log_limit=50):
    """What the FreeRADIUS tab and `fabricctl radius status` show: on/off,
    the server name supplicants check, the RADIUS clients (never their
    secrets) and the recent decisions. Read-only."""
    on = bool(v.get("install_freeradius"))
    out = {"enabled": on, "server_name": v.get("hostname_radius", ""), "host_ip": v.get("host_ip", ""),
           "clients": [{"name": c.get("name"), "address": c.get("address"),
                        "message_authenticator": c.get("message_authenticator", True)}
                       for c in v.get("radius_clients") or []],
           "log": [], "log_error": ""}
    if on:
        try:
            out["log"] = list_auth_log(log_limit)
        except Exception as exc:          # journal unreadable: the tab still shows the rest
            out["log_error"] = f"the auth log could not be read: {exc}"
    return out
