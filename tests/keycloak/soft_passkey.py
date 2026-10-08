"""A software passkey for the keycloak suite (manual 2.3.6.2.6.2): what a browser and a platform authenticator (Windows
Hello, a phone) hand Keycloak's WebAuthn forms, with an ES256 key in memory. It always reports user verification (the
PIN or fingerprint), so it stands for an unlocked device. Attestation "none". Test code only."""
import base64
import hashlib
import json
import os
import re

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec


def b64url(data):
    """Base64url without padding, as Keycloak's forms take it."""
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _cbor(value):
    """The few CBOR types WebAuthn needs here: unsigned and negative ints, bytes, text, maps."""
    def head(major, n):
        if n < 24:
            return bytes([major << 5 | n])
        for size, code in ((1, 24), (2, 25), (4, 26), (8, 27)):
            if n < 1 << (8 * size):
                return bytes([major << 5 | code]) + n.to_bytes(size, "big")
        raise ValueError(n)
    if isinstance(value, int):
        return head(0, value) if value >= 0 else head(1, -1 - value)
    if isinstance(value, bytes):
        return head(2, len(value)) + value
    if isinstance(value, str):
        return head(3, len(value.encode())) + value.encode()
    if isinstance(value, dict):
        return head(5, len(value)) + b"".join(_cbor(k) + _cbor(v) for k, v in value.items())
    raise TypeError(type(value))


def page_value(page, name):
    """A value from the script block of Keycloak's WebAuthn page ("name : "value"")."""
    m = re.search(rf'\b{name}\s*:\s*"([^"]*)"', page)
    return m.group(1) if m else ""


class SoftPasskey:
    """One passkey on one device: registered once, then used to sign in."""

    def __init__(self, origin):
        self.origin, self.key, self.cred_id, self.counter = origin, ec.generate_private_key(ec.SECP256R1()), \
            os.urandom(32), 0

    def _client_data(self, kind, challenge):
        return json.dumps({"type": kind, "challenge": challenge, "origin": self.origin, "crossOrigin": False},
                          separators=(",", ":")).encode()

    def register(self, page):
        """The registration form's fields for Keycloak's webauthn-register page."""
        rp_id, challenge = page_value(page, "rpId"), page_value(page, "challenge")
        nums = self.key.public_key().public_numbers()
        cose = {1: 2, 3: -7, -1: 1, -2: nums.x.to_bytes(32, "big"), -3: nums.y.to_bytes(32, "big")}
        auth = (hashlib.sha256(rp_id.encode()).digest() + bytes([0x45]) + (0).to_bytes(4, "big") + bytes(16)
                + len(self.cred_id).to_bytes(2, "big") + self.cred_id + _cbor(cose))   # flags: UP, UV, AT
        att = _cbor({"fmt": "none", "attStmt": {}, "authData": auth})
        return {"clientDataJSON": b64url(self._client_data("webauthn.create", challenge)),
                "attestationObject": b64url(att), "publicKeyCredentialId": b64url(self.cred_id),
                "authenticatorLabel": "soft passkey", "transports": "internal", "authenticatorAttachment": "platform",
                "error": ""}

    def sign_in(self, page, key=None):
        """The sign-in form's fields for Keycloak's webauthn-authenticator page (key: sign with another key)."""
        rp_id, challenge = page_value(page, "rpId"), page_value(page, "challenge")
        self.counter += 1
        auth = hashlib.sha256(rp_id.encode()).digest() + bytes([0x05]) + self.counter.to_bytes(4, "big")  # UP, UV
        client = self._client_data("webauthn.get", challenge)
        sig = (key or self.key).sign(auth + hashlib.sha256(client).digest(), ec.ECDSA(hashes.SHA256()))
        return {"clientDataJSON": b64url(client), "authenticatorData": b64url(auth), "signature": b64url(sig),
                "credentialId": b64url(self.cred_id), "userHandle": page_value(page, "userid") or "", "error": ""}
