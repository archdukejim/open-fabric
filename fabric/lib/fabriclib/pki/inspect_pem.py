import subprocess
import tempfile

from fabriclib.common.errors import ValidationError
from fabriclib.pki.common.ca_files import ca_files
from fabriclib.pki.common.describe_cert import describe_cert
from fabriclib.pki.common.openssl import openssl
from fabriclib.pki.common.to_pem import to_pem
from fabriclib.pki.describe_csr import describe_csr


def inspect_pem(v, data):
    """Decode certificates (PEM chain, DER or base64) or a CSR for reading.
    Certificates are checked against this fabric's CA. Private keys are
    refused unread. Returns {kind: 'cert' | 'csr', items: [{info, text,
    trusted}]} (CSR items carry describe_csr's policy verdict)."""
    raw = data if isinstance(data, str) else data.decode("latin-1")
    if "PRIVATE KEY" in raw:
        raise ValidationError("that is a private key: it was not read or stored. Inspect the certificate instead.")
    try:
        certs = to_pem(data, "cert")
    except ValidationError:
        certs = []
    if certs:
        root, intermediate = ca_files(v)
        items = []
        for pem in certs[:10]:
            with tempfile.NamedTemporaryFile("w", suffix=".pem") as f:
                f.write(pem)
                f.flush()
                trusted = subprocess.run(["openssl", "verify", "-CAfile", root, "-untrusted", intermediate, f.name],
                                         capture_output=True).returncode == 0
            items.append({"info": describe_cert(pem), "trusted": trusted,
                          "text": openssl("x509", "-noout", "-text", data=pem)})
        return {"kind": "cert", "items": items}
    req = describe_csr(data)
    return {"kind": "csr", "items": [{"info": {k: req[k] for k in ("subject", "sans", "key", "ca_requested",
                                                                      "problems")},
                                      "trusted": None, "text": req["text"]}]}
