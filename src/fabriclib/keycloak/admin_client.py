import time


class Admin:
    """A Keycloak admin REST client that logs in as the master-realm admin on first use (and again before the token
    expires). Every call goes through a TLS connection pinned to the fabric root CA."""

    def __init__(self, tls, user, password):
        """Purpose: a Keycloak admin REST client that logs in as the master-realm admin on first use.
        Inputs:  tls — a webui.tlsclient.TLSClient pinned to the fabric root CA; user, password — str, the Keycloak
                 admin credentials from fabric's secrets (never on a command line).
        Returns: None (no request is made yet; token and expiry start empty).
        Fails:   never.
        Feeds:   configure_keycloak, keycloak_admin, user_has_role; tests/keycloak/verify.py,
                 tests/host/reset_user.py."""
        self.tls, self.user, self.password = tls, user, password
        self.token, self.expires = None, 0

    def _auth(self):
        """Purpose: get or refresh the admin access token (password grant, client admin-cli, master realm).
        Inputs:  none; uses self.tls, self.user, self.password; reuses the token until 15 s before it expires.
        Returns: None; sets self.token and self.expires.
        Fails:   SystemExit("Keycloak admin login failed (<status>): <body>") on any non-200 reply; OSError/ssl errors
                 from the TLS connection propagate.
        Feeds:   Admin.call."""
        if self.token and time.time() < self.expires - 15:
            return
        status, body = self.tls.request("POST", "/realms/master/protocol/openid-connect/token", form={
            "grant_type": "password", "client_id": "admin-cli",
            "username": self.user, "password": self.password})
        if status != 200:
            raise SystemExit(f"Keycloak admin login failed ({status}): {body}")
        self.token = body["access_token"]
        self.expires = time.time() + int(body.get("expires_in", 60))

    def call(self, method, path, body=None, ok=(200, 201, 204), allow=()):
        """Purpose: make one authenticated call to the admin API under /admin/realms.
        Inputs:  method — HTTP method; path — str appended to /admin/realms (callers quote names with q); body —
                 JSON-able object or None; ok — statuses treated as success (default 200, 201, 204); allow — extra
                 statuses returned to the caller instead of failing (e.g. 404).
        Returns: (status, payload) — payload is parsed JSON, text, or {"location": ...} for an empty reply with
                 Location.
        Fails:   SystemExit("<method> <path> failed (<status>): <payload>") for any other status; SystemExit from
                 _auth; OSError/ssl errors from the connection.
        Feeds:   every ensure_* step in fabriclib/keycloak, grant_role_to_group and the admin helpers;
                 tests/keycloak/verify.py."""
        self._auth()
        status, payload = self.tls.request(method, "/admin/realms" + path, body=body,
                                           headers={"Authorization": f"Bearer {self.token}"})
        if status in allow:
            return status, payload
        if status not in ok:
            raise SystemExit(f"{method} {path} failed ({status}): {payload}")
        return status, payload
