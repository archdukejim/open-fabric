import urllib.error
import urllib.request

from fabriclib.common.errors import ValidationError
from fabriclib.pki.common.describe_cert import describe_cert
from fabriclib.pki.common.to_pem import to_pem


def fetch_pinned_root(address, root_sha256, port=80, timeout=20):
    """Purpose: get the upstream's root CA certificate and accept it only if it is the one the invitation
             pinned. Fetched over plain HTTP from the upstream's certificates page (fabric publishes it there
             on purpose): the fingerprint, not the transport, makes it trustworthy.
    Inputs:  address — the upstream's IP (from the invitation); root_sha256 — "AA:BB:..." (the invitation);
             port — default 80; timeout — seconds, default 20.
    Returns: the root's PEM (str).
    Fails:   ValidationError "cannot reach the upstream at <address> (...)"; "the upstream sent no certificate";
             "the upstream's root CA is not the one in the invitation (someone in between, or a stale
             invitation)".
    Feeds:   join_upstream (before any TLS call: the root is then the only trust anchor)."""
    host = f"[{address}]" if ":" in address else address
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/certs/root-ca.crt", timeout=timeout) as r:
            body = r.read(65536).decode("ascii", "replace")
    except (urllib.error.URLError, OSError) as e:
        raise ValidationError(f"cannot reach the upstream at {address} ({e})") from None
    try:
        pem = to_pem(body, "cert")[0]
    except (ValidationError, IndexError):
        raise ValidationError("the upstream sent no certificate") from None
    if describe_cert(pem)["sha256"].upper() != root_sha256.upper():
        raise ValidationError("the upstream's root CA is not the one in the invitation "
                              "(someone in between, or a stale invitation)")
    return pem
