"""Minimal OIDC authorization-code + PKCE client for Keycloak (stdlib only).

ID tokens arrive directly from the token endpoint over the CA-pinned TLS
channel, and are additionally verified: RS256 signature against the realm
JWKS, issuer, audience, azp, expiry and nonce.
"""
import base64
import hashlib
import hmac
import json
import secrets
import time
import urllib.parse

CLOCK_SKEW = 60
# ASN.1 DigestInfo prefix for SHA-256 (RFC 8017 §9.2)
SHA256_DIGEST_INFO = bytes.fromhex("3031300d060960864801650304020105000420")


class OIDCError(Exception):
    pass


def b64url_decode(data):
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def b64url_encode(data):
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def rs256_verify(signing_input, signature, n, e):
    """RSASSA-PKCS1-v1_5 with SHA-256."""
    k = (n.bit_length() + 7) // 8
    if len(signature) != k:
        return False
    em = pow(int.from_bytes(signature, "big"), e, n).to_bytes(k, "big")
    t = SHA256_DIGEST_INFO + hashlib.sha256(signing_input).digest()
    if k < len(t) + 11:
        return False
    expected = b"\x00\x01" + b"\xff" * (k - len(t) - 3) + b"\x00" + t
    return hmac.compare_digest(em, expected)


class KeycloakOIDC:
    def __init__(self, client, public_base, realm, client_id, client_secret, redirect_uri):
        """client: TLSClient to Keycloak. public_base: https://sso.example.com"""
        self.client = client
        self.realm_path = f"/realms/{urllib.parse.quote(realm)}"
        self.issuer = f"{public_base}{self.realm_path}"
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self._jwks = {}
        self._jwks_fetched = 0

    # -- login ---------------------------------------------------------
    def start_login(self):
        """Return (authorization URL, state, nonce, code_verifier)."""
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        verifier = secrets.token_urlsafe(64)
        challenge = b64url_encode(hashlib.sha256(verifier.encode()).digest())
        query = urllib.parse.urlencode({
            "client_id": self.client_id,
            "response_type": "code",
            "scope": "openid",
            "redirect_uri": self.redirect_uri,
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "prompt": "login",
        })
        return f"{self.issuer}/protocol/openid-connect/auth?{query}", state, nonce, verifier

    def finish_login(self, code, verifier, nonce):
        status, tokens = self.client.request(
            "POST", f"{self.realm_path}/protocol/openid-connect/token",
            form={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": self.redirect_uri,
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code_verifier": verifier,
            })
        if status != 200 or not isinstance(tokens, dict) or "id_token" not in tokens:
            raise OIDCError(f"token exchange failed ({status})")
        claims = self.verify_id_token(tokens["id_token"], nonce)
        return claims, tokens["id_token"]

    def logout_url(self, id_token, post_logout_redirect):
        query = urllib.parse.urlencode({
            "id_token_hint": id_token,
            "post_logout_redirect_uri": post_logout_redirect,
            "client_id": self.client_id,
        })
        return f"{self.issuer}/protocol/openid-connect/logout?{query}"

    # -- token validation ----------------------------------------------
    def _key(self, kid):
        if kid not in self._jwks and time.time() - self._jwks_fetched > 30:
            status, jwks = self.client.request("GET", f"{self.realm_path}/protocol/openid-connect/certs")
            if status != 200:
                raise OIDCError(f"JWKS fetch failed ({status})")
            self._jwks_fetched = time.time()
            self._jwks = {
                k["kid"]: (int.from_bytes(b64url_decode(k["n"]), "big"),
                           int.from_bytes(b64url_decode(k["e"]), "big"))
                for k in jwks.get("keys", [])
                if k.get("kty") == "RSA" and k.get("use", "sig") == "sig"
            }
        if kid not in self._jwks:
            raise OIDCError("unknown signing key")
        return self._jwks[kid]

    def verify_id_token(self, token, nonce):
        try:
            header_b64, payload_b64, sig_b64 = token.split(".")
            header = json.loads(b64url_decode(header_b64))
            claims = json.loads(b64url_decode(payload_b64))
            signature = b64url_decode(sig_b64)
        except (ValueError, json.JSONDecodeError) as exc:
            raise OIDCError("malformed ID token") from exc
        if header.get("alg") != "RS256":
            raise OIDCError(f"unexpected alg {header.get('alg')}")
        n, e = self._key(header.get("kid"))
        if not rs256_verify(f"{header_b64}.{payload_b64}".encode(), signature, n, e):
            raise OIDCError("bad ID token signature")

        now = time.time()
        aud = claims.get("aud")
        auds = aud if isinstance(aud, list) else [aud]
        checks = [
            (claims.get("iss") == self.issuer, "issuer mismatch"),
            (self.client_id in auds, "audience mismatch"),
            (claims.get("azp", self.client_id) == self.client_id, "azp mismatch"),
            (float(claims.get("exp", 0)) > now - CLOCK_SKEW, "token expired"),
            (float(claims.get("iat", now)) < now + CLOCK_SKEW, "token issued in the future"),
            (hmac.compare_digest(str(claims.get("nonce", "")), nonce), "nonce mismatch"),
        ]
        for ok, msg in checks:
            if not ok:
                raise OIDCError(msg)
        return claims
