"""Slot type "pkcs11": the vault key encrypted to an RSA key that lives on a
security key or smart card (YubiKey PIV, Nitrokey, SmartCard-HSM, any
PKCS#11 token) and can never be read out of it.

The wrap is RSA-OAEP (SHA-1, the digest every token supports; OAEP's
security does not rest on collision resistance) done by the token. The
ciphertext sits in the slot store; only the token can turn it back into
the key. The token's PIN is kept root-only on this host
(`pin-<slot id>`, 0400): the token is the factor, like a stick, but its key
cannot be copied. The token is identified by its PKCS#11 serial through a
library from the allowed list."""
import base64
import os

from fabriclib.vault.common.find_token import find_token
from fabriclib.vault.common.pkcs11_session import pkcs11_session
from fabriclib.vault.common.write_private_file import write_private_file

TESTED = "SoftHSM2 software token (generate, wrap, unwrap, PIN guard, rotate, remove); YubiKey/Nitrokey untested"
ALG = "RSA-OAEP-SHA1"


def pin_path(v, slot):
    return os.path.join(v["openbao_key_dir"], f"pin-{slot['id']}")


def save_pin(v, slot, pin):
    write_private_file(pin_path(v, slot), pin.encode(), 0, 0, 0o400)


def _pin(v, slot):
    with open(pin_path(v, slot)) as f:
        return f.read()


def _keys(P, session, key_id):
    """(public, private) handles for the key pair with CKA_ID `key_id` (hex)."""
    ident = tuple(bytes.fromhex(key_id))

    def one(cls):
        found = session.findObjects([(P.CKA_CLASS, cls), (P.CKA_ID, ident)])
        return found[0] if found else None
    return one(P.CKO_PUBLIC_KEY), one(P.CKO_PRIVATE_KEY)


def _mech(P):
    return P.RSAOAEPMechanism(P.CKM_SHA_1, P.CKG_MGF1_SHA1)


def wrap(v, slot, key, key_id, attended=True):
    dev = slot["device"]
    with pkcs11_session(dev["module"], dev["token_serial"], _pin(v, slot), attended) as (P, session, _):
        public, _private = _keys(P, session, dev["key_id"])
        if public is None:
            raise ValueError("the key pair is no longer on the token")
        ct = bytes(session.encrypt(public, key, _mech(P)))
    return {"alg": ALG, "ciphertext": base64.b64encode(ct).decode()}


def unwrap(v, slot, record, attended=False):
    dev = slot["device"]
    with pkcs11_session(dev["module"], dev["token_serial"], _pin(v, slot), attended) as (P, session, _):
        _public, private = _keys(P, session, dev["key_id"])
        if private is None or record.get("alg") != ALG:
            return None
        return bytes(session.decrypt(private, base64.b64decode(record["ciphertext"]), _mech(P)))


def present(v, slot):
    dev = slot["device"]
    return find_token(dev["module"], dev["token_serial"]) is not None


def forget(v, slot, record):
    """Nothing to destroy: the wrapped copy is only the ciphertext in the
    store, which goes with the record. The key pair stays on the token."""


def discard(v, slot):
    """The method is gone: delete its stored PIN."""
    path = pin_path(v, slot)
    if os.path.exists(path):
        os.remove(path)
