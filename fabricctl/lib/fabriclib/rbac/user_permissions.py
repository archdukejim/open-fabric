from fabriclib.rbac.permissions import PERMISSIONS, PREFIX


def user_permissions(claims):
    """Purpose: The fabric permissions a verified token grants.
    Inputs:  claims — verified ID-token claims (dict); reads "roles" (Keycloak also lists a composite
             role's permissions there).
    Returns: set of permission names without the "fabric:" prefix, limited to known PERMISSIONS.
    Fails:   never for a verified token (non-str roles are ignored).
    Feeds:   agent/handler.py Handler.authorize (the permission check and self.perms, which decides
             reset_sign_in's `privileged`).
    """
    roles = claims.get("roles") or []
    return {r[len(PREFIX):] for r in roles if isinstance(r, str) and r.startswith(PREFIX)
            and r[len(PREFIX):] in PERMISSIONS}
