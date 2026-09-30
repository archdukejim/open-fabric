import re
import secrets
import urllib.parse

from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.keycloak.keycloak_admin import keycloak_admin
from fabriclib.secrets.load_secrets import load_secrets

UID_RE = re.compile(r"^[a-z][a-z0-9._-]{1,31}$")
NAME_RE = re.compile(r"^[\w .,'-]{1,60}$")
MAIL_RE = re.compile(r"^[^@\s]{1,64}@[A-Za-z0-9.-]{1,190}\.[A-Za-z]{2,}$")


def _q(s):
    return urllib.parse.quote(s, safe="")


def create_person(v, actor, uid, first, last, email, source="web"):
    """A new realm user (helpdesk, `people:create`): created in Keycloak,
    which writes the account to 389-DS, member of the plain `users` group
    only (never a fabric group), with a one-time password that must be
    changed at the first sign-in (TOTP enrolment follows). Returns that
    password; it is shown once and stored nowhere."""
    if not UID_RE.match(uid or ""):
        raise ValidationError("user name: 2-32 characters, a-z 0-9 . _ -, starting with a letter")
    if not NAME_RE.match(first or "") or not NAME_RE.match(last or ""):
        raise ValidationError("first and last name: letters and simple punctuation, at most 60")
    if not MAIL_RE.match(email or ""):
        raise ValidationError("e-mail address looks wrong")
    password = secrets.token_urlsafe(15)
    try:
        kc, realm = keycloak_admin(v, load_secrets())
        r = _q(realm)
        status, _ = kc.call("POST", f"/{r}/users", {"username": uid, "firstName": first, "lastName": last,
                                                     "email": email, "enabled": True, "emailVerified": False},
                            allow=(409,))
        if status == 409:
            raise ValidationError(f"{uid} (or that e-mail address) already exists")
        user = kc.call("GET", f"/{r}/users?username={_q(uid)}&exact=true")[1][0]
        kc.call("PUT", f"/{r}/users/{user['id']}/reset-password",
                {"type": "password", "value": password, "temporary": True})
        group = next((g for g in kc.call("GET", f"/{r}/groups?search=users&exact=true")[1] if g["name"] == "users"),
                     None)
        if group:
            kc.call("PUT", f"/{r}/users/{user['id']}/groups/{group['id']}")
    except SystemExit as exc:                 # the admin client's way of saying Keycloak refused
        raise ValidationError(f"Keycloak refused: {exc}")
    write_audit(actor, "PERSON_CREATE", f"user={uid}", source)
    return password
