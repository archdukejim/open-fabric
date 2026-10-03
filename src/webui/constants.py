"""The web UI's fixed limits and names."""

SESSION_COOKIE = "__Host-webui"
LOGIN_COOKIE = "__Host-webui-login"
MAX_BODY = 64 * 1024
LOGIN_TTL = 600
STEP_UP = 300                    # vault changes need a sign-in no older than this (seconds)
PERM_PREFIX = "fabric:"          # fabric's permission roles (fabriclib/rbac/permissions.py)
REFRESH_BEFORE = 60              # renew the ID token this many seconds before it expires
