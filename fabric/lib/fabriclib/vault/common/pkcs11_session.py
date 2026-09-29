import contextlib

from fabriclib.common.errors import ValidationError
from fabriclib.vault.common.find_token import find_token


@contextlib.contextmanager
def pkcs11_session(module, serial, pin, attended=False):
    """A logged-in session on the token, closed afterwards.

    PIN retries are precious (a YubiKey locks its PIV applet after three).
    A locked PIN or a last try is never used. Unattended (fabric-unlock at
    boot, the kill switch) a token that already saw a wrong PIN is not tried
    either, so a stale stored PIN costs one try, not all of them; a person
    running `vault test` clears that with one correct login."""
    found = find_token(module, serial)
    if not found:
        raise ValidationError("the security key is not plugged in")
    P, lib, slot, info = found
    if info.flags & P.CKF_USER_PIN_LOCKED:
        raise ValidationError("the token's PIN is locked: reset it with the vendor tool (PUK), then re-add the key")
    if info.flags & P.CKF_USER_PIN_FINAL_TRY:
        raise ValidationError("one PIN try left on the token: fabric will not spend it; check the PIN with the vendor tool")
    if not attended and info.flags & P.CKF_USER_PIN_COUNT_LOW:
        raise ValidationError("the token saw a wrong PIN: not retried unattended; run `fabricctl vault test` once")
    session = lib.openSession(slot, P.CKF_SERIAL_SESSION | P.CKF_RW_SESSION)
    try:
        try:
            session.login(pin)
        except P.PyKCS11Error as exc:
            if exc.value == P.CKR_PIN_INCORRECT:
                raise ValidationError("wrong PIN for the security key")
            raise ValidationError(f"the security key refused the login ({exc})")
        try:
            yield P, session, info
        finally:
            session.logout()
    finally:
        session.closeSession()
