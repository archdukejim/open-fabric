"""HTTPS client pinned to the core root CA.

Services on core_net are reached by container IP (the host may not resolve
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
        ctx = ssl.create_default_context(cafile=ca_file)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        super().__init__(ip, port, context=ctx, timeout=timeout)
        self._server_hostname = server_hostname

    def connect(self):
        sock = socket.create_connection((self.host, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self._server_hostname)


class TLSClient:
    def __init__(self, ip, port, hostname, ca_file):
        self.ip, self.port, self.hostname, self.ca_file = ip, port, hostname, ca_file

    def request(self, method, path, body=None, headers=None, form=None):
        """Return (status, parsed JSON or text). `form` sends urlencoded data."""
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
