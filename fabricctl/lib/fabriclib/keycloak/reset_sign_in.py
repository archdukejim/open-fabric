import secrets
import urllib.parse

from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.keycloak.fabric_groups import fabric_groups
from fabriclib.keycloak.keycloak_admin import keycloak_admin
from fabriclib.secrets.load_secrets import load_secrets


def _q(s):
    """Purpose: URL-encode one path or query component for the Keycloak admin API (nothing kept, not "/").
    Inputs:  s — str (a realm, user name, client id or role name).
    Returns: the percent-encoded str.
    Fails:   never for a str.
    Feeds:   reset_sign_in.
    """
    return urllib.parse.quote(s, safe="")


def reset_sign_in(v, actor, uid, privileged=False, source="web"):
    """Purpose: Helpdesk `people:reset`: give a person a new one-time password, remove their TOTP (they
             enrol again) and end their sessions.
    Inputs:  v — fabric vars (keycloak_admin, fabric_groups); actor — str, for the audit; uid — username
             (exact match); privileged — bool: the caller is root or holds system:admin (admin bundle);
             source — default "web". Reads Keycloak admin credentials via load_secrets.
    Returns: the new one-time password (token_urlsafe(15)): shown once, stored nowhere.
    Fails:   ValidationError "no user <uid>"; "<uid> is in a fabric group (...): only an admin can reset
             their sign-in"; "Keycloak refused: ..." (admin API error or failed login); load_secrets'
             ValidationError; OSError / ssl errors if Keycloak is unreachable.
    Feeds:   agent route POST /v1/people/<uid>/reset -> webui agentclient.reset_sign_in -> People page.
    Notes:   members of fabric groups (admins, auditors, operators, ...) need `privileged`: otherwise the
             helpdesk could take over an admin's single sign-on (OpenBao's UI needs no client certificate).
             Audited as PERSON_RESET.
    """
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
