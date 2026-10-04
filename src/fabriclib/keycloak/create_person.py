import os
import re
import urllib.parse

from fabriclib.common.errors import ValidationError
from fabriclib.common.one_time_password import one_time_password
from fabriclib.common.write_audit import write_audit
from fabriclib.keycloak.keycloak_admin import keycloak_admin
from fabriclib.ldap.ensure_posix_identities import ensure_posix_identities
from fabriclib.ldap.people_written_here import people_written_here
from fabriclib.secrets.load_secrets import load_secrets

UID_RE = re.compile(r"^[a-z][a-z0-9._-]{1,31}$")
NAME_RE = re.compile(r"^[\w .,'-]{1,60}$")
MAIL_RE = re.compile(r"^[^@\s]{1,64}@[A-Za-z0-9.-]{1,190}\.[A-Za-z]{2,}$")


def _q(s):
    """Purpose: URL-encode one path or query component for the Keycloak admin API (nothing kept, not "/").
    Inputs:  s — str (a realm, user name, client id or role name).
    Returns: the percent-encoded str.
    Fails:   never for a str.
    Feeds:   create_person.
    """
    return urllib.parse.quote(s, safe="")


def create_person(v, actor, uid, first, last, email, source="web"):
    """Purpose: Helpdesk `people:create`: create a realm user in Keycloak (which writes the account to
             389-DS) with a one-time password.
    Inputs:  v — fabric vars (keycloak_admin: ip_keycloak, hostname_keycloak, webui_realm or domain, root
             CA); actor — str, for the audit; uid — ^[a-z][a-z0-9._-]{1,31}$; first, last — letters and
             simple punctuation, 1-60 characters; email — an address with a dotted domain; source — audit
             source, default "web". Reads the Keycloak admin credentials via load_secrets (file or OpenBao).
    Returns: the one-time password (common/one_time_password: every character kind 389-DS asks for): shown once, stored
             nowhere. The person also gets their
             POSIX identity at once (ldap/ensure_posix_identities; if that fails, the 5-minute timer gives it).
    Fails:   ValidationError "people are created at the root site …" at a federated site (M5: the directory is a
             read-only copy there); "user name: 2-32 characters, ..."; "first and last name: ..."; "e-mail address
             looks wrong"; "<uid> (or that e-mail address) already exists" (HTTP 409); "Keycloak refused:
             ..." (any other admin API error or failed admin login, raised as SystemExit by
             admin_client.Admin); load_secrets' ValidationError (OpenBao sealed or unreachable);
             OSError / ssl errors if Keycloak is unreachable; IndexError if the new user cannot be read back.
    Feeds:   agent route POST /v1/people (agent/post_route.py) -> webui
             agentclient.create_person -> People page.
    Notes:   the user joins the plain `users` group only (never a fabric group; skipped silently if that
             group does not exist). The password is temporary: Keycloak asks for a new one, then TOTP
             enrolment, at the first sign-in. If a step after the creation fails the account stays, without
             a known password (reset_sign_in recovers it). Audited as PERSON_CREATE.
    """
    if not people_written_here(os.path.join(v["deploy_base_dir"], "fabric", "config", "federation.yaml")):
        raise ValidationError("people are created at the root site of the federation: this site holds a read-only "
                              "copy of the directory")
    if not UID_RE.match(uid or ""):
        raise ValidationError("user name: 2-32 characters, a-z 0-9 . _ -, starting with a letter")
    if not NAME_RE.match(first or "") or not NAME_RE.match(last or ""):
        raise ValidationError("first and last name: letters and simple punctuation, at most 60")
    if not MAIL_RE.match(email or ""):
        raise ValidationError("e-mail address looks wrong")
    password = one_time_password()
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
    try:                                      # their POSIX identity now; else the 5-minute timer gives it
        ensure_posix_identities(v)
    except (ValidationError, RuntimeError):
        pass
    write_audit(actor, "PERSON_CREATE", f"user={uid}", source)
    return password
