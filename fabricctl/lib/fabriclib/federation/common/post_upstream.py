import http.client
import json
import socket
import ssl

from fabriclib.common.errors import ValidationError


class _PinnedConnection(http.client.HTTPSConnection):
    """HTTPS to an address while naming the host (SNI, certificate name, Host header) separately: a joining
    node does not resolve the upstream's names yet."""

    def __init__(self, address, host, port, context, timeout):
        """Purpose: remember where to connect as well as which name to ask for.
        Inputs:  address — IP to connect to; host — the name the certificate must carry; port; context — an
                 ssl.SSLContext; timeout — seconds.
        Returns: None.
        Fails:   never.
        Feeds:   post_upstream."""
        super().__init__(host, port, context=context, timeout=timeout)
        self._address = address

    def connect(self):
        """Purpose: open the TCP connection to the address and run TLS for the host name.
        Inputs:  none.
        Returns: None; self.sock is the TLS socket.
        Fails:   OSError / ssl.SSLError (connection refused, timeout, certificate not trusted or wrong name).
        Feeds:   http.client (on the first request)."""
        sock = socket.create_connection((self._address, self.port), self.timeout)
        self.sock = self._context.wrap_socket(sock, server_hostname=self.host)


def post_upstream(address, host, root_pem, path, body, port=443, timeout=120):
    """Purpose: POST JSON to the upstream's federation endpoint over TLS verified against the pinned root
             (never unverified), and return its JSON answer.
    Inputs:  address — the upstream's IP; host — its federation host name (the certificate must name it);
             root_pem — the pinned root (fetch_pinned_root), the only trust anchor; path — e.g. "/v1/join";
             body — dict; port — default 443; timeout — seconds, default 120 (signing runs a container).
    Returns: the decoded JSON answer (dict) of a 200.
    Fails:   ValidationError "the upstream refused: <its message>" (a 4xx/5xx with an error); "cannot reach the
             upstream's federation endpoint at <host> (<address>): ..." (network or TLS, including a
             certificate not from the pinned root or not naming host); "the upstream's answer is not JSON".
    Feeds:   join_upstream."""
    ctx = ssl.create_default_context(cadata=root_pem)
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    conn = _PinnedConnection(address, host, port, ctx, timeout)
    try:
        conn.request("POST", path, body=json.dumps(body), headers={"Content-Type": "application/json"})
        res = conn.getresponse()
        raw = res.read(1024 * 1024)
    except (OSError, ssl.SSLError, http.client.HTTPException) as e:
        raise ValidationError(f"cannot reach the upstream's federation endpoint at {host} ({address}): {e}") from None
    finally:
        conn.close()
    try:
        answer = json.loads(raw)
    except ValueError:
        raise ValidationError(f"the upstream's answer is not JSON (HTTP {res.status})") from None
    if res.status != 200:
        raise ValidationError(f"the upstream refused: {answer.get('error') if isinstance(answer, dict) else answer}")
    return answer
