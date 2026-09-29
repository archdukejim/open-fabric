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
    return os.path.join(v["openbao_key_dir"], f"kmip-{slot['id']}")


def _session(v, slot, timeout=10):
    dev, d = slot["device"], slot_dir(v, slot)
    host, _, port = dev["endpoint"].rpartition(":")
    return kmip_session(host, port, dev.get("server_name") or host, os.path.join(d, "ca.crt"),
                        os.path.join(d, "client.crt"), os.path.join(d, "client.key"), timeout)


def _params():
    from kmip import enums
    return {"cryptographic_algorithm": enums.CryptographicAlgorithm.AES,
            "block_cipher_mode": enums.BlockCipherMode.CBC, "padding_method": enums.PaddingMethod.PKCS5}


def wrap(v, slot, key, key_id, attended=True):
    iv = os.urandom(16)
    with _session(v, slot) as client:
        ct, _ = client.encrypt(key, uid=slot["device"]["key_uid"], cryptographic_parameters=_params(),
                               iv_counter_nonce=iv)
    return {"alg": ALG, "iv": base64.b64encode(iv).decode(), "ciphertext": base64.b64encode(ct).decode()}


def unwrap(v, slot, record, attended=False):
    if record.get("alg") != ALG:
        return None
    with _session(v, slot) as client:
        return bytes(client.decrypt(base64.b64decode(record["ciphertext"]), uid=slot["device"]["key_uid"],
                                    cryptographic_parameters=_params(),
                                    iv_counter_nonce=base64.b64decode(record["iv"])))


def present(v, slot):
    try:
        with _session(v, slot, timeout=5):
            return True
    except Exception:
        return False


def forget(v, slot, record):
    """Nothing to destroy: the wrapped copy is only the ciphertext in the store."""


def discard(v, slot):
    """The method is gone: delete its certificates and key."""
    shutil.rmtree(slot_dir(v, slot), ignore_errors=True)
