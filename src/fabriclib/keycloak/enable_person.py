import urllib.parse

from fabriclib.common.errors import ValidationError
from fabriclib.keycloak.keycloak_admin import keycloak_admin


def enable_person(v, secrets, uid):
    """Purpose: let Keycloak sign a person in again after their directory account is enabled (manual 1.6.3.16):
             a sign-in tried while the account was disabled makes Keycloak's AD mapper mark its own copy of the
             user disabled, and that copy stays so until it is enabled here.
    Inputs:  v — fabric vars (keycloak_admin's); secrets — fabric's secrets (keycloak_admin_user/password); uid — the
             user name.
    Returns: int, how many Keycloak users were enabled (0 when Keycloak never saw them or already had them enabled).
    Fails:   ValidationError "Keycloak refused: …"; OSError / ssl errors if Keycloak is unreachable.
    Feeds:   directory/set_person_enabled."""
    changed = 0
    try:
        kc, realm = keycloak_admin(v, secrets)
        r, u = urllib.parse.quote(realm, safe=""), urllib.parse.quote(uid, safe="")
        for user in kc.call("GET", f"/{r}/users?username={u}&exact=true")[1]:
            if not user.get("enabled", True):
                kc.call("PUT", f"/{r}/users/{user['id']}", {**user, "enabled": True})
                changed += 1
    except SystemExit as exc:                # the admin client's way of saying Keycloak refused
        raise ValidationError(f"Keycloak refused: {exc}")
    return changed
