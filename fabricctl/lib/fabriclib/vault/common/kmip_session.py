import contextlib
import ssl
import types

from fabriclib.common.errors import ValidationError


@contextlib.contextmanager
def kmip_session(host, port, server_name, ca_file, cert_file, key_file, timeout=10):
    """Purpose: context manager giving an open PyKMIP client on a mutual-TLS connection that fabric builds itself.
    Inputs:  host, port — the KMIP server (port as str or int); server_name — name its certificate must carry;
             ca_file — CA that must have signed it; cert_file, key_file — fabric's client certificate and key (paths);
             timeout — socket timeout in seconds (10).
    Returns: yields an opened kmip.pie.client.ProxyKmipClient; closed on exit (errors while closing are ignored).
    Fails:   ValidationError if python3-pykmip is missing, or if connecting or the TLS handshake fails (any exception
             from client.open(), e.g. a server certificate that does not verify). Errors in the with block propagate.
    Feeds:   slots/kmip._session (wrap, unwrap, present), tests/openbao/run.py.
    Notes:   PyKMIP's own TLS code is replaced (its proxy's _create_socket): it does not verify the server
             certificate (it ORs cert_reqs into the context options). Here: TLS 1.2+, CA and server name verified.
    """
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
