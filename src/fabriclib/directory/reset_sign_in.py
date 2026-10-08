import urllib.parse

from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.directory.people_password import people_password
from fabriclib.directory.run_op import run_op
from fabriclib.keycloak.fabric_groups import fabric_groups
from fabriclib.keycloak.keycloak_admin import keycloak_admin
from fabriclib.secrets.load_secrets import load_secrets


def reset_sign_in(v, actor, uid, privileged=False, source="web", secrets=None):
    """Purpose: Helpdesk `people:reset` (manual 1.6.3.8): a person's new one-time password in the directory (they
             change it at their next sign-in; their account is unlocked), their TOTP removed in Keycloak (they enrol
             again) and their sessions ended.
    Inputs:  v — fabric vars (site_name, ad_password_policy, fabric_groups, keycloak_admin's); actor — str, for the
             audit; uid — the user name; privileged — bool: the caller is root or holds system:admin; source —
             default "web"; secrets — fabric's secrets (default: load_secrets()).
    Returns: the new one-time password: shown once, stored nowhere.
    Fails:   ValidationError "no such entry" (no such person); "<uid> is in a fabric group (…): only an admin can
             reset their sign-in"; the directory's refusals (another site's person); "Keycloak refused: …";
             load_secrets' errors; OSError / ssl errors if Keycloak is unreachable.
    Feeds:   agent route POST /v1/people/<uid>/reset -> webui agentclient.reset_sign_in -> People page.
    Notes:   members of fabric groups need `privileged`: otherwise the helpdesk could take over an admin's single
             sign-on. Audited as PERSON_RESET."""
    secrets = secrets if secrets is not None else load_secrets()
    person = run_op(v, secrets, "get_person", {"uid": uid})
    held = sorted(set(person["groups"]) & fabric_groups(v))
    if held and not privileged:
        raise ValidationError(f"{uid} is in a fabric group ({', '.join(held)}): only an admin can reset their sign-in")
    password = people_password(v)
    run_op(v, secrets, "reset_password", {"uid": uid, "password": password})
    try:
        kc, realm = keycloak_admin(v, secrets)
        r, u = urllib.parse.quote(realm, safe=""), urllib.parse.quote(uid, safe="")
        for user in kc.call("GET", f"/{r}/users?username={u}&exact=true")[1]:
            for cred in kc.call("GET", f"/{r}/users/{user['id']}/credentials")[1]:
                if cred.get("type") == "otp":
                    kc.call("DELETE", f"/{r}/users/{user['id']}/credentials/{cred['id']}")
            kc.call("POST", f"/{r}/users/{user['id']}/logout")
    except SystemExit as exc:                 # the admin client's way of saying Keycloak refused
        raise ValidationError(f"Keycloak refused: {exc}")
    write_audit(actor, "PERSON_RESET", f"user={uid} (password, TOTP, sessions)", source)
    return password
