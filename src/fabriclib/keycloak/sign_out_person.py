import urllib.parse

from fabriclib.common.errors import ValidationError
from fabriclib.keycloak.keycloak_admin import keycloak_admin


def sign_out_person(v, secrets, uid, drop_otp=False, delete=False):
    """Purpose: end a person's Keycloak sessions at once (manual 1.6.3.8, 1.6.3.16): after a reset, a disable or a
             removal, no single sign-on they already hold keeps working.
    Inputs:  v — fabric vars (keycloak_admin's); secrets — fabric's secrets (keycloak_admin_user/password); uid — the
             user name; drop_otp — also remove their TOTP (a reset: they enrol again); delete — also delete Keycloak's
             copy of the user (a removal; the directory account is removed by the caller).
    Returns: int, how many Keycloak users matched (0 when Keycloak never saw them, or already dropped its copy).
    Fails:   ValidationError "Keycloak refused: …"; OSError / ssl errors if Keycloak is unreachable.
    Feeds:   directory/reset_sign_in, directory/set_person_enabled, directory/remove_person."""
    try:
        kc, realm = keycloak_admin(v, secrets)
        r, u = urllib.parse.quote(realm, safe=""), urllib.parse.quote(uid, safe="")
        users = kc.call("GET", f"/{r}/users?username={u}&exact=true")[1]
        for user in users:
            if drop_otp:
                for cred in kc.call("GET", f"/{r}/users/{user['id']}/credentials")[1]:
                    if cred.get("type") == "otp":
                        kc.call("DELETE", f"/{r}/users/{user['id']}/credentials/{cred['id']}")
            kc.call("POST", f"/{r}/users/{user['id']}/logout")
            if delete:                       # gone already when Keycloak noticed the directory account is
                kc.call("DELETE", f"/{r}/users/{user['id']}", allow=(404,))
    except SystemExit as exc:                # the admin client's way of saying Keycloak refused
        raise ValidationError(f"Keycloak refused: {exc}")
    return len(users)
