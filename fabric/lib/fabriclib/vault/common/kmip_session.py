import contextlib
import ssl
import types

from fabriclib.common.errors import ValidationError


@contextlib.contextmanager
def kmip_session(host, port, server_name, ca_file, cert_file, key_file, timeout=10):
    """An open KMIP client (PyKMIP's ProxyKmipClient) on a TLS connection
    fabric makes itself: TLS 1.2+, the server certificate verified against
    `ca_file` and `server_name`, fabric's client certificate. PyKMIP's own
    TLS code is not used: it does not verify the server certificate
    (it ORs cert_reqs into the context options)."""
    try:
        from kmip.pie.client import ProxyKmipClient
    except ImportError:
        raise ValidationError("KMIP needs python3-pykmip: sudo apt install python3-pykmip")

    def tls(self, sock):
        ctx = ssl.create_default_context(cafile=ca_file)
        ctx.minimum_version = ssl.TLSVersion.TLSv1_2
        ctx.load_cert_chain(cert_file, key_file)
        self.socket = ctx.wrap_socket(sock, server_hostname=server_name)
        self.socket.settimeout(timeout)

    client = ProxyKmipClient(hostname=host, port=int(port), config_file="/dev/null")
    client.proxy._create_socket = types.MethodType(tls, client.proxy)
    client.proxy.timeout = timeout
    try:
        client.open()
    except Exception as exc:
        raise ValidationError(f"KMIP server {host}:{port} not reachable or refused the TLS handshake: {exc}")
    try:
        yield client
    finally:
        try:
            client.close()
        except Exception:
            pass
