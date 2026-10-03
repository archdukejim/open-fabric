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
    """Purpose: where one security-key method's PIN is kept.
    Inputs:  v — vars: openbao_key_dir; slot — slot dict (its id).
    Returns: <openbao_key_dir>/pin-<slot id> (str).
    Fails:   KeyError if a field is missing; nothing else.
    Feeds:   save_pin, _pin, discard.
    """
    return os.path.join(v["openbao_key_dir"], f"pin-{slot['id']}")


def save_pin(v, slot, pin):
    """Purpose: keep the token's PIN root-only (0400) on this host, so unattended unlocks can log in.
    Inputs:  v — vars; slot — pkcs11 slot; pin — the PIN (str).
    Returns: None.
    Fails:   OSError from write_private_file.
    Feeds:   add_security_key_slot, tests/openbao/run.py.
    """
    write_private_file(pin_path(v, slot), pin.encode(), 0, 0, 0o400)


def _pin(v, slot):
    """Purpose: read the stored PIN of a slot.
    Inputs:  v — vars; slot — pkcs11 slot; reads pin-<slot id>.
    Returns: the PIN (str).
    Fails:   FileNotFoundError or PermissionError (OSError) if the PIN file is missing or not readable.
    Feeds:   wrap, unwrap.
    """
    with open(pin_path(v, slot)) as f:
        return f.read()


def _keys(P, session, key_id):
    """Purpose: find the key pair with a given CKA_ID on the token.
    Inputs:  P — PyKCS11 module; session — logged-in session; key_id — the CKA_ID in hex.
    Returns: (public key handle or None, private key handle or None).
    Fails:   ValueError if key_id is not hex; PyKCS11Error from the token.
    Feeds:   wrap, unwrap.
    """
    ident = tuple(bytes.fromhex(key_id))

    def one(cls):
        found = session.findObjects([(P.CKA_CLASS, cls), (P.CKA_ID, ident)])
        return found[0] if found else None
    return one(P.CKO_PUBLIC_KEY), one(P.CKO_PRIVATE_KEY)


def _mech(P):
    """Purpose: the wrap mechanism: RSA-OAEP with SHA-1 and MGF1-SHA1.
    Inputs:  P — PyKCS11 module.
    Returns: a PyKCS11 RSAOAEPMechanism.
    Fails:   never — only builds an object.
    Feeds:   wrap, unwrap.
    Notes:   SHA-1 is the digest every token supports; OAEP's security does not rest on collision resistance.
    """
    return P.RSAOAEPMechanism(P.CKM_SHA_1, P.CKG_MGF1_SHA1)


def wrap(v, slot, key, key_id, attended=True):
    """Purpose: encrypt the vault key to the RSA key pair on the token (RSA-OAEP, done by the token).
    Inputs:  v — vars; slot — pkcs11 slot: device.module, device.token_serial, device.key_id, and its stored PIN;
             key — vault key (bytes); key_id — its version (not used here);
             attended — passed to pkcs11_session (default True).
    Returns: wrap record {"alg": "RSA-OAEP-SHA1", "ciphertext": base64}.
    Fails:   ValueError if the key pair is no longer on the token; ValidationError from pkcs11_session (absent,
             PIN locked, last try, wrong PIN, ...); OSError reading the PIN; PyKCS11Error from the token.
    Feeds:   add_security_key_slot, rotate_vault_key (through slot_type).
    """
    dev = slot["device"]
    with pkcs11_session(dev["module"], dev["token_serial"], _pin(v, slot), attended) as (P, session, _):
        public, _private = _keys(P, session, dev["key_id"])
        if public is None:
            raise ValueError("the key pair is no longer on the token")
        ct = bytes(session.encrypt(public, key, _mech(P)))
    return {"alg": ALG, "ciphertext": base64.b64encode(ct).decode()}


def unwrap(v, slot, record, attended=False):
    """Purpose: have the token decrypt a wrap record with its private key, which never leaves it.
    Inputs:  v — vars; slot — pkcs11 slot; record — the wrap record;
             attended — False for boot and the kill switch (a token that saw a wrong PIN is then not tried),
               True when a person asked.
    Returns: the key (bytes), or None if the private key is gone or the record's alg is not RSA-OAEP-SHA1.
    Fails:   ValidationError from pkcs11_session; OSError reading the PIN; PyKCS11Error from decrypt.
    Feeds:   obtain_key (through slot_type), add_security_key_slot (read-back check).
    """
    dev = slot["device"]
    with pkcs11_session(dev["module"], dev["token_serial"], _pin(v, slot), attended) as (P, session, _):
        _public, private = _keys(P, session, dev["key_id"])
        if private is None or record.get("alg") != ALG:
            return None
        return bytes(session.decrypt(private, base64.b64decode(record["ciphertext"]), _mech(P)))


def present(v, slot):
    """Purpose: tell whether the enrolled token is plugged in (no login, no PIN try spent).
    Inputs:  v — not used; slot — pkcs11 slot: device.module, device.token_serial.
    Returns: True if find_token sees it, else False.
    Fails:   ValidationError (no PyKCS11) or PyKCS11Error from find_token; list_slots and vault_device_event catch them.
    Feeds:   list_slots, vault_device_event (through slot_type).
    """
    dev = slot["device"]
    return find_token(dev["module"], dev["token_serial"]) is not None


def forget(v, slot, record):
    """Purpose: destroy this method's copy of one key version; for a token there is nothing to destroy.
    Inputs:  v, slot, record — as for unwrap (not used).
    Returns: None.
    Fails:   never — does nothing.
    Feeds:   remove_slot, rotate_vault_key (through slot_type).
    Notes:   the wrapped copy is only the ciphertext in the store, which goes with the record.
             The key pair stays on the token.
    """


def discard(v, slot):
    """Purpose: clean up once the whole method is gone: delete its stored PIN (the key pair stays on the token).
    Inputs:  v — vars; slot — pkcs11 slot.
    Returns: None.
    Fails:   OSError if the PIN file exists but cannot be removed.
    Feeds:   remove_slot, rotate_vault_key (dropped methods), add_security_key_slot (rollback when enrolment fails).
    """
    path = pin_path(v, slot)
    if os.path.exists(path):
        os.remove(path)
