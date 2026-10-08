"""The web UI's fixed limits and names."""

SESSION_COOKIE = "__Host-webui"
LOGIN_COOKIE = "__Host-webui-login"
MAX_BODY = 64 * 1024
LOGIN_TTL = 600
STEP_UP = 300                    # vault changes need a sign-in no older than this (seconds)
PERM_PREFIX = "fabric:"          # fabric's permission roles (fabriclib/rbac/permissions.py)
REFRESH_BEFORE = 60              # renew the ID token this many seconds before it expires
# stands for the certificate while the web console requires none (webui_client_cert off, manual 2.3.6.2.6.3): no CN to
# match the user, no fingerprint to bind the session to (the session cookie and the ID token bind it)
NO_CERT = {"cn": None, "fp": ""}
