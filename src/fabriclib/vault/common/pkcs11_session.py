import contextlib

from fabriclib.common.errors import ValidationError
from fabriclib.vault.common.find_token import find_token


@contextlib.contextmanager
def pkcs11_session(module, serial, pin, attended=False):
    """Purpose: context manager giving a logged-in PKCS#11 session on one token; logs out and closes it afterwards.
    Inputs:  module — allowed library path; serial — token serial; pin — the user PIN (str);
             attended — True when a person asked for this: a token that saw a wrong PIN is then still tried.
    Returns: yields (PyKCS11 module, session, token info).
    Fails:   ValidationError: the token is not plugged in; its PIN is locked; only one try is left (never spent);
             it saw a wrong PIN and this is unattended; wrong PIN (CKR_PIN_INCORRECT); any other login refusal.
             From find_token: ValidationError (no PyKCS11) or PyKCS11Error. Errors in the with block propagate.
    Feeds:   slots/pkcs11 wrap and unwrap, add_security_key_slot.
    Notes:   PIN retries are precious (a YubiKey locks its PIV applet after three). Unattended (fabric-unlock at
             boot, the kill switch) a token that already saw a wrong PIN is not tried, so a stale stored PIN costs
             one try, not all of them; a person running `vault test` clears that with one correct login.
    """
    found = find_token(module, serial)
    if not found:
        raise ValidationError("the security key is not plugged in")
    P, lib, slot, info = found
    if info.flags & P.CKF_USER_PIN_LOCKED:
        raise ValidationError("the token's PIN is locked: reset it with the vendor tool (PUK), then re-add the key")
    if info.flags & P.CKF_USER_PIN_FINAL_TRY:
        raise ValidationError("one PIN try left on the token: fabric will not spend it; "
                              "check the PIN with the vendor tool")
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
