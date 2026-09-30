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
    """Purpose: Decode base64url text whose '=' padding was stripped (JWT parts, JWKS n/e).
    Inputs:  data — str in the base64url alphabet, padding optional.
    Returns: the decoded bytes.
    Fails:   binascii.Error (a ValueError) on an impossible length; ValueError for non-ASCII text; TypeError if data
             is not a str. Characters outside the alphabet are silently dropped (non-validating decode).
    Feeds:   verify_id_token (header, claims, signature) and KeycloakOIDC._key (modulus, exponent).
    """
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))


def b64url_encode(data):
    """Purpose: Encode bytes as base64url without '=' padding.
    Inputs:  data — bytes.
    Returns: the encoded str.
    Fails:   TypeError if data is not bytes-like.
    Feeds:   KeycloakOIDC.start_login (the PKCE S256 code_challenge).
    """
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def rs256_verify(signing_input, signature, n, e):
    """Purpose: Check an RSASSA-PKCS1-v1_5 signature with SHA-256 (JWT alg RS256) using only the standard library.
    Inputs:  signing_input — bytes, the ASCII 'header.payload' of the JWT; signature — bytes; n — int RSA modulus; e
             — int public exponent.
    Returns: True if the signature is valid; False on a wrong signature length, a key too small for the encoding, or
             any mismatch.
    Fails:   never for int n, e and bytes inputs — every problem is a False return.
    Feeds:   KeycloakOIDC.verify_id_token.
    Notes:   It builds the full expected encoding (00 01 FF.. 00 DigestInfo hash) and compares it in constant time
             with hmac.compare_digest, rather than parsing the decrypted block, which avoids the classic PKCS#1 v1.5
             parsing forgeries.
    """
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
        """Purpose: Configure the OIDC client for one Keycloak realm and one confidential client.
        Inputs:  client — TLSClient to Keycloak; public_base — str, public Keycloak URL such as
                 https://sso.example.com (issuer and browser URLs); realm — str realm name (URL-quoted into paths);
                 client_id — str; client_secret — str; redirect_uri — str, the registered callback URL (webui:
                 <public_url>/oidc/callback).
        Returns: None (constructor); the JWKS cache starts empty.
        Fails:   never — it only stores and formats values.
        Feeds:   server.App.__init__ (self.oidc) and fabriclib/keycloak/verify_user_token._client (fabric-agent).
        """
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
        """Purpose: Begin an authorization-code login with PKCE: fresh state, nonce and code verifier, and the Keycloak
                 URL to send the browser to.
        Inputs:  none (uses issuer, client_id and redirect_uri).
        Returns: (authorization URL str, state str, nonce str, code_verifier str).
        Fails:   never.
        Feeds:   server.Handler.login, which stores state, nonce and verifier in App.pending and redirects to the
                 URL.
        Notes:   prompt=login makes Keycloak ask for the password (and TOTP) every time, even with an SSO session, so
                 auth_time is fresh for the vault step-up check.
        """
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
        """Purpose: Exchange the authorization code for tokens (with the client secret and PKCE verifier) and verify the
                 ID token, including its nonce.
        Inputs:  code — str from the callback query; verifier — str, the code_verifier from start_login; nonce — str,
                 the nonce from start_login.
        Returns: (claims dict, id_token str, refresh_token str — "" if Keycloak sent none).
        Fails:   OIDCError 'token exchange failed (<status>)' when the status is not 200 or no id_token came back;
                 OIDCError from verify_id_token; OSError / ssl.SSLError from TLSClient.request propagate.
        Feeds:   server.Handler.callback.
        """
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
        return claims, tokens["id_token"], tokens.get("refresh_token", "")

    def refresh(self, refresh_token):
        """Purpose: Get a fresh ID token (with the person's current roles) from a refresh token.
        Inputs:  refresh_token — str from the previous token response.
        Returns: (claims dict, id_token str, refresh_token str — the new one, or the old one if Keycloak sent none).
        Fails:   OIDCError 'refresh refused (<status>)' when the SSO session was ended, the user disabled or the
                 token expired; OIDCError from verify_id_token (no nonce check); OSError / ssl.SSLError from
                 TLSClient.request propagate.
        Feeds:   server.Handler.renew.
        """
        status, tokens = self.client.request(
            "POST", f"{self.realm_path}/protocol/openid-connect/token",
            form={"grant_type": "refresh_token", "refresh_token": refresh_token,
                  "client_id": self.client_id, "client_secret": self.client_secret})
        if status != 200 or not isinstance(tokens, dict) or "id_token" not in tokens:
            raise OIDCError(f"refresh refused ({status})")
        claims = self.verify_id_token(tokens["id_token"])
        return claims, tokens["id_token"], tokens.get("refresh_token", refresh_token)

    def logout_url(self, id_token, post_logout_redirect):
        """Purpose: Build the Keycloak end-session URL that signs the person out of the realm.
        Inputs:  id_token — str, sent as id_token_hint; post_logout_redirect — str URL Keycloak returns to (must be
                 registered for the client).
        Returns: the logout URL str.
        Fails:   never.
        Feeds:   server.Handler.post (/logout), which redirects the browser there.
        """
        query = urllib.parse.urlencode({
            "id_token_hint": id_token,
            "post_logout_redirect_uri": post_logout_redirect,
            "client_id": self.client_id,
        })
        return f"{self.issuer}/protocol/openid-connect/logout?{query}"

    # -- token validation ----------------------------------------------
    def _key(self, kid):
        """Purpose: Look up the realm's RSA signing key by key id, fetching the JWKS when the id is not cached.
        Inputs:  kid — the 'kid' from the token header (str or None). Reads and refreshes self._jwks and
                 self._jwks_fetched.
        Returns: (n, e) — the key's modulus and exponent as ints.
        Fails:   OIDCError 'JWKS fetch failed (<status>)'; OIDCError 'unknown signing key' when the id is not in the
                 set, including within 30 s of the last fetch (no refetch then); AttributeError / KeyError if a 200
                 response is not a JWKS object or a key lacks kid, n or e; OSError / ssl.SSLError from
                 TLSClient.request.
        Feeds:   verify_id_token.
        Notes:   Only RSA keys meant for signatures are kept. A refetch replaces the whole cache, so keys Keycloak
                 rotated out stop being accepted; the 30 s gap stops unknown kids from forcing a fetch on every
                 request.
        """
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

    def verify_id_token(self, token, nonce=None):
        """Purpose: Verify an ID token and return its claims: RS256 signature against the realm JWKS, issuer, audience,
                 azp, expiry, issue time and (optionally) nonce.
        Inputs:  token — str, compact JWT; nonce — str to match the 'nonce' claim on the login response, or None to
                 skip it (refreshed tokens, fetched directly over the pinned channel, and fabric-agent's check of
                 forwarded tokens).
        Returns: the claims dict.
        Fails:   OIDCError with 'malformed ID token', 'unexpected alg <alg>', 'bad ID token signature', 'issuer
                 mismatch', 'audience mismatch', 'azp mismatch', 'token expired', 'token issued in the future' or
                 'nonce mismatch'; OIDCError from _key. Not wrapped: AttributeError if token is not a str or the
                 header/claims are not JSON objects, ValueError / TypeError from float() on a non-numeric exp or iat.
        Feeds:   finish_login, refresh, and fabriclib/keycloak/verify_user_token (fabric-agent authenticates each web
                 UI call with it).
        Notes:   60 s clock skew (CLOCK_SKEW) is allowed on exp and iat. A missing azp is accepted; a missing iat
                 counts as now.
        """
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
            (nonce is None or hmac.compare_digest(str(claims.get("nonce", "")), nonce), "nonce mismatch"),
        ]
        for ok, msg in checks:
            if not ok:
                raise OIDCError(msg)
        return claims
