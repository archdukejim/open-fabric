import secrets
import urllib.parse

from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.keycloak.fabric_groups import fabric_groups
from fabriclib.keycloak.keycloak_admin import keycloak_admin
from fabriclib.secrets.load_secrets import load_secrets


def _q(s):
    return urllib.parse.quote(s, safe="")


def reset_sign_in(v, actor, uid, privileged=False, source="web"):
    """Reset a person's sign-in (helpdesk, `people:reset`): a new one-time
    password (changed at the next sign-in), their TOTP removed (enrolled
    again), their sessions ended. Someone in a fabric group (admins,
    auditors, operators, …) can only be reset with `privileged` (the admin
    bundle): otherwise the helpdesk could take over an admin's single
    sign-on (OpenBao's UI needs no client certificate). Returns the
    password, shown once and stored nowhere."""
    password = secrets.token_urlsafe(15)
    try:
        kc, realm = keycloak_admin(v, load_secrets())
        r = _q(realm)
        found = kc.call("GET", f"/{r}/users?username={_q(uid)}&exact=true")[1]
        if not found:
            raise ValidationError(f"no user {uid}")
        user = found[0]
        groups = {g["name"] for g in kc.call("GET", f"/{r}/users/{user['id']}/groups")[1]}
        held = sorted(groups & fabric_groups(v))
        if held and not privileged:
            raise ValidationError(f"{uid} is in a fabric group ({', '.join(held)}): only an admin can reset their sign-in")
        for cred in kc.call("GET", f"/{r}/users/{user['id']}/credentials")[1]:
            if cred.get("type") == "otp":
                kc.call("DELETE", f"/{r}/users/{user['id']}/credentials/{cred['id']}")
        kc.call("PUT", f"/{r}/users/{user['id']}/reset-password",
                {"type": "password", "value": password, "temporary": True})
        kc.call("POST", f"/{r}/users/{user['id']}/logout")
    except SystemExit as exc:
        raise ValidationError(f"Keycloak refused: {exc}")
    write_audit(actor, "PERSON_RESET", f"user={uid} (password, TOTP, sessions)", source)
    return password
