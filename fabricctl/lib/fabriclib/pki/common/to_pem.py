import base64
import re

from fabriclib.common.errors import ValidationError
from fabriclib.pki.common.openssl import openssl

BLOCK_RE = re.compile(r"-----BEGIN ([A-Z0-9 ]+)-----\r?\n.*?-----END \1-----", re.S)


def to_pem(data, kind):
    """Purpose: Normalise an uploaded or pasted certificate, CSR or key to PEM text, so every PKI
             operation works on PEM.
    Inputs:  data — str (PEM, or bare base64 DER as some devices show it) or bytes (a DER upload, or PEM
             sent as bytes); kind — "cert" | "csr" | "key" (PRIVATE KEY, RSA PRIVATE KEY, EC PRIVATE KEY;
             encrypted keys are not matched).
    Returns: list of PEM blocks (str, each ending in a newline) of that kind in input order (a chain gives
             several; blocks of other kinds are ignored); [] for empty or blank text.
    Fails:   ValidationError "no <kind> found in the input" (PEM without a block of that kind); "not a PEM
             or DER <kind>" (neither PEM nor base64 DER openssl accepts); openssl's first error line for
             non-ASCII bytes openssl cannot parse as DER; KeyError for an unknown kind.
    Feeds:   ca_summary, common/ca_chain_pem, convert_cert, describe_csr, inspect_pem, issue_key_pair,
             sign_csr.
    """
    if isinstance(data, bytes):
        try:
            data = data.decode("ascii")
        except UnicodeDecodeError:
            cmd = {"cert": ("x509", "-inform", "DER"), "csr": ("req", "-inform", "DER"),
                   "key": ("pkey", "-inform", "DER")}[kind]
            return [openssl(*cmd, data=data).decode()]
    text = data.replace("\r\n", "\n").strip()
    if not text:
        return []
    if "-----BEGIN" not in text:
        try:                                    # bare base64 DER, as some devices show it
            return to_pem(base64.b64decode(re.sub(r"\s+", "", text), validate=True), kind)
        except ValueError:
            raise ValidationError(f"not a PEM or DER {kind}")
    want = {"cert": ("CERTIFICATE",), "csr": ("CERTIFICATE REQUEST", "NEW CERTIFICATE REQUEST"),
            "key": ("PRIVATE KEY", "RSA PRIVATE KEY", "EC PRIVATE KEY")}[kind]
    blocks = [m.group(0) + "\n" for m in BLOCK_RE.finditer(text) if m.group(1) in want]
    if not blocks:
        raise ValidationError(f"no {kind} found in the input")
    return blocks
