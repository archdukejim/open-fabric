from fabriclib.rbac.permissions import PERMISSIONS, PREFIX


def user_permissions(claims):
    """The fabric permissions in a verified token's `roles` claim (Keycloak
    puts a composite role's permissions there too)."""
    roles = claims.get("roles") or []
    return {r[len(PREFIX):] for r in roles if isinstance(r, str) and r.startswith(PREFIX)
            and r[len(PREFIX):] in PERMISSIONS}
