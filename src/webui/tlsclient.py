"""HTTPS client pinned to the core root CA.

Services on fabric_net are reached by container IP (the host may not resolve
core hostnames), but the certificate is still verified against the expected
hostname and the core root CA only — never the system trust store.
"""
import http.client
import json
import socket
import ssl
import urllib.parse


class PinnedHTTPSConnection(http.client.HTTPSConnection):
    def __init__(self, ip, port, server_hostname, ca_file, timeout=15):
        """Purpose: Set up an HTTPS connection to a container IP whose certificate is checked against one CA file and an
                 expected hostname, not against the IP.
        Inputs:  ip — str, address to connect to; port — int; server_hostname — str, the name the certificate must
                 carry (also sent as SNI); ca_file — str, path to the PEM root CA, the only trust anchor; timeout —
                 seconds for connect and reads, default 15.
        Returns: None (constructor).
        Fails:   FileNotFoundError or ssl.SSLError from ssl.create_default_context when ca_file is missing or not a
                 readable PEM CA.
        Feeds:   TLSClient.request, which creates one connection per request.
        Notes:   TLS 1.2 minimum. Passing cafile means the system trust store is not loaded; hostname checking stays
                 on (the create_default_context default).
        """
        ctx = ssl.create_default_context(cafile=ca_file)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        super().__init__(ip, port, context=ctx, timeout=timeout)
        self._server_hostname = server_hostname

    def connect(self):
        """Purpose: Open the TCP connection to the IP and wrap it in TLS, verifying the certificate for server_hostname
                 instead of the IP.
        Inputs:  none (uses self.host, self.port, self.timeout, self._context and self._server_hostname).
        Returns: None; sets self.sock.
        Fails:   OSError / socket.timeout from socket.create_connection; ssl.SSLCertVerificationError or ssl.SSLError
                 when the certificate is not from the CA or not for server_hostname. They propagate through
                 http.client to TLSClient.request's caller.
        Feeds:   http.client.HTTPConnection.request, which calls it implicitly.
        """
        sock = socket.create_connection((self.host, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self._server_hostname)


class TLSClient:
    def __init__(self, ip, port, hostname, ca_file):
        """Purpose: Remember where a CA-pinned HTTPS service lives: container IP, port, public hostname and CA file.
        Inputs:  ip — str, container IP; port — int (Keycloak: 8443); hostname — str, the service's public name
                 (certificate check, Host and X-Forwarded-Host); ca_file — str, path to the fabric root CA PEM.
        Returns: None (constructor).
        Fails:   never — it only stores the values; a bad CA path shows up on the first request.
        Feeds:   request; built by server.App.__init__, src/ux/cli/keycloak_bootstrap.py, fabriclib/keycloak/
                 (keycloak_admin, user_has_role, verify_user_token) and
                 tests/keycloak/verify.py, tests/host/reset_user.py.
        """
        self.ip, self.port, self.hostname, self.ca_file = ip, port, hostname, ca_file

    def request(self, method, path, body=None, headers=None, form=None):
        """Purpose: Send one HTTPS request to the pinned service and return the status with the body parsed as JSON when
                 it is JSON.
        Inputs:  method — str HTTP verb; path — str path with query; body — JSON-serialisable object sent as
                 application/json (ignored when form is given); headers — dict of extra headers (Host,
                 X-Forwarded-Host, X-Forwarded-Proto and X-Forwarded-Port default to hostname / https / 443); form —
                 dict sent as application/x-www-form-urlencoded.
        Returns: (status int, payload): payload is the parsed JSON, the raw text if it is not JSON, None for an empty
                 body, or {"location": <Location header>} when the body is empty and a Location header is set.
        Fails:   It does not check the status (callers do). OSError / socket.timeout (15 s) on connect or read,
                 ssl.SSLError on a certificate or hostname mismatch, http.client.HTTPException on a malformed
                 response, TypeError from json.dumps for a body that is not serialisable.
        Feeds:   KeycloakOIDC.finish_login, refresh and _key; keycloak_bootstrap.Admin (the Keycloak admin API used
                 by fabriclib/keycloak/ and setup).
        Notes:   The X-Forwarded-* headers make Keycloak build URLs (issuer, redirects) from the public name,
                 although it is reached by container IP.
        """
        headers = dict(headers or {})
        headers.setdefault("Host", self.hostname)
        # Keycloak builds URLs from the forwarded host; match the public name.
        headers.setdefault("X-Forwarded-Host", self.hostname)
        headers.setdefault("X-Forwarded-Proto", "https")
        headers.setdefault("X-Forwarded-Port", "443")
        data = None
        if form is not None:
            data = urllib.parse.urlencode(form).encode()
            headers["Content-Type"] = "application/x-www-form-urlencoded"
        elif body is not None:
            data = json.dumps(body).encode()
            headers["Content-Type"] = "application/json"
        conn = PinnedHTTPSConnection(self.ip, self.port, self.hostname, self.ca_file)
        try:
            conn.request(method, path, body=data, headers=headers)
            resp = conn.getresponse()
            raw = resp.read()
            location = resp.getheader("Location")
        finally:
            conn.close()
        text = raw.decode("utf-8", "replace")
        try:
            payload = json.loads(text) if text else None
        except ValueError:
            payload = text
        if location and payload is None:
            payload = {"location": location}
        return resp.status, payload
