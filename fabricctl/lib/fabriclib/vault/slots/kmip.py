"""Slot type "kmip": the vault key encrypted by an AES key that lives in an
HSM or key manager (any KMIP server: CipherTrust, Fortanix, Entrust,
IBM GKLM, Cosmian, …) and never leaves it.

The device does the Encrypt/Decrypt (AES-256-CBC, PKCS#5 padding, a random
IV per wrap; the unwrapped key is checked against the stored check value,
so a wrong or tampered result is refused). fabric connects with mutual TLS:
the server's certificate verified against the CA given at enrolment,
fabric's own client certificate. Its files (ca.crt, client.crt,
client.key) are root-only in <openbao_key_dir>/kmip-<slot id>/. Revoking
fabric's client or disabling the key on the device is the kill switch."""
import base64
import os
import shutil

from fabriclib.vault.common.kmip_session import kmip_session

TESTED = "PyKMIP server (Encrypt/Decrypt AES-CBC over mutual TLS, rotate, revoke); vendor HSMs untested"
ALG = "AES-256-CBC-PKCS5"


def slot_dir(v, slot):
    """Purpose: the folder that holds one KMIP method's CA certificate, client certificate and client key.
    Inputs:  v — vars: openbao_key_dir; slot — slot dict (its id).
    Returns: <openbao_key_dir>/kmip-<slot id> (str); nothing is checked or created.
    Fails:   KeyError if openbao_key_dir or the slot id is missing; nothing else.
    Feeds:   _session, discard, add_kmip_slot (writes ca.crt, client.crt and client.key there, root 0400).
    """
    return os.path.join(v["openbao_key_dir"], f"kmip-{slot['id']}")


def _session(v, slot, timeout=10):
    """Purpose: a KMIP session to this slot's device with the slot's stored certificates.
    Inputs:  v — vars; slot — kmip slot: device.endpoint "host:port", device.server_name (else the host), and
               ca.crt, client.crt, client.key in slot_dir; timeout — seconds (10).
    Returns: the kmip_session context manager, not yet entered.
    Fails:   on entering: ValidationError from kmip_session (PyKMIP missing, unreachable, TLS refused).
    Feeds:   wrap, unwrap, present.
    """
    dev, d = slot["device"], slot_dir(v, slot)
    host, _, port = dev["endpoint"].rpartition(":")
    return kmip_session(host, port, dev.get("server_name") or host, os.path.join(d, "ca.crt"),
                        os.path.join(d, "client.crt"), os.path.join(d, "client.key"), timeout)


def _params():
    """Purpose: the cryptographic parameters for Encrypt/Decrypt on the device: AES, CBC mode, PKCS#5 padding.
    Inputs:  none.
    Returns: dict of PyKMIP enums for the cryptographic_parameters argument.
    Fails:   ImportError if PyKMIP is not installed (kmip_session has already refused by then).
    Feeds:   wrap, unwrap.
    """
    from kmip import enums
    return {"cryptographic_algorithm": enums.CryptographicAlgorithm.AES,
            "block_cipher_mode": enums.BlockCipherMode.CBC, "padding_method": enums.PaddingMethod.PKCS5}


def wrap(v, slot, key, key_id, attended=True):
    """Purpose: encrypt the vault key with the device's AES key; that key never leaves the device.
    Inputs:  v — vars; slot — kmip slot (device.key_uid names the AES key); key — vault key (bytes);
             key_id — its version (not used here); attended — not used (same signature as the other types).
    Returns: wrap record {"alg": "AES-256-CBC-PKCS5", "iv": base64, "ciphertext": base64}; a random IV per wrap.
    Fails:   ValidationError from kmip_session; PyKMIP exceptions (e.g. KmipOperationFailure) if the device refuses
             Encrypt with that key.
    Feeds:   add_kmip_slot, rotate_vault_key (through slot_type).
    """
    iv = os.urandom(16)
    with _session(v, slot) as client:
        ct, _ = client.encrypt(key, uid=slot["device"]["key_uid"], cryptographic_parameters=_params(),
                               iv_counter_nonce=iv)
    return {"alg": ALG, "iv": base64.b64encode(iv).decode(), "ciphertext": base64.b64encode(ct).decode()}


def unwrap(v, slot, record, attended=False):
    """Purpose: have the device decrypt a wrap record back into the vault key.
    Inputs:  v — vars; slot — kmip slot; record — a wrap record from wrap; attended — not used.
    Returns: the key (bytes), or None if the record's alg is not AES-256-CBC-PKCS5. The caller checks the result
             against the stored check value, so a wrong or tampered result is refused there.
    Fails:   ValidationError from kmip_session; PyKMIP exceptions if the device refuses Decrypt (fabric's client
             revoked or the key disabled: the kill switch); binascii.Error or KeyError for a malformed record.
    Feeds:   obtain_key (through slot_type), add_kmip_slot (read-back check).
    """
    if record.get("alg") != ALG:
        return None
    with _session(v, slot) as client:
        return bytes(client.decrypt(base64.b64decode(record["ciphertext"]), uid=slot["device"]["key_uid"],
                                    cryptographic_parameters=_params(),
                                    iv_counter_nonce=base64.b64decode(record["iv"])))


def present(v, slot):
    """Purpose: tell whether the device can be reached now, by opening and closing a session (5 s timeout).
    Inputs:  v — vars; slot — kmip slot.
    Returns: True if the mutual-TLS session opened, else False.
    Fails:   never — every exception is caught and gives False.
    Feeds:   list_slots, vault_device_event (through slot_type).
    """
    try:
        with _session(v, slot, timeout=5):
            return True
    except Exception:
        return False


def forget(v, slot, record):
    """Purpose: destroy this method's copy of one key version; for KMIP there is nothing to destroy.
    Inputs:  v, slot, record — as for unwrap (not used).
    Returns: None.
    Fails:   never — does nothing.
    Feeds:   remove_slot, rotate_vault_key (through slot_type).
    Notes:   the wrapped copy is only the ciphertext in the store, which goes with the record.
    """


def discard(v, slot):
    """Purpose: clean up once the whole method is gone: delete its certificates and client key.
    Inputs:  v — vars; slot — kmip slot.
    Returns: None.
    Fails:   never — errors while deleting are ignored.
    Feeds:   remove_slot, rotate_vault_key (dropped methods), add_kmip_slot (rollback when enrolment fails).
    """
    shutil.rmtree(slot_dir(v, slot), ignore_errors=True)
