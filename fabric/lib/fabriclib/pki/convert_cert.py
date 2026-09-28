import base64
import os
import secrets
import subprocess
import tempfile

from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.pki.common.ca_chain_pem import ca_chain_pem
from fabriclib.pki.common.ca_files import ca_files
from fabriclib.pki.common.describe_cert import describe_cert
from fabriclib.pki.common.openssl import openssl
from fabriclib.pki.common.safe_name import safe_name
from fabriclib.pki.common.to_pem import to_pem
from fabriclib.pki.export_p12 import export_p12


def _write(tmp, name, body):
    path = os.path.join(tmp, name)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(body)
    return path


def convert_cert(v, actor, cert_data, key_data="", source="web"):
    """Re-package a certificate for devices that want another format: PEM
    (.crt), DER (.cer), the full chain (.pem, .p7b) and — given its private
    key — a password-protected .p12. A certificate issued by this fabric gets
    the fabric chain appended; any other keeps the chain it came with. The
    key is used in memory/0600 temp files only and not kept. Returns {name,
    cert, fullchain, der_b64, p7b_b64, p12_b64, p12_password, info}."""
    certs = to_pem(cert_data, "cert")
    if not certs:
        raise ValidationError("no certificate given")
    leaf, rest = certs[0], certs[1:]
    info = describe_cert(leaf)
    root, intermediate = ca_files(v)
    with tempfile.TemporaryDirectory(prefix="fabric-convert-") as tmp:      # 0700
        leaf_path = _write(tmp, "leaf.pem", leaf)
        ours = subprocess.run(["openssl", "verify", "-CAfile", root, "-untrusted", intermediate, leaf_path],
                              capture_output=True).returncode == 0
        chain = ca_chain_pem(v) if ours else "".join(rest)
        fullchain = leaf + chain
        p7b = openssl("crl2pkcs7", "-nocrl", "-certfile", _write(tmp, "full.pem", fullchain), "-outform", "DER",
                      data=b"")
        out = {"name": safe_name(info["subject"].partition("CN=")[2].split(",")[0] or "certificate"),
               "cert": leaf, "fullchain": fullchain, "info": info, "fabric_issued": ours,
               "der_b64": base64.b64encode(openssl("x509", "-outform", "DER", data=leaf.encode())).decode(),
               "p7b_b64": base64.b64encode(p7b).decode(), "p12_b64": "", "p12_password": ""}
        if key_data and key_data.strip():
            keys = to_pem(key_data, "key")
            if len(keys) != 1:
                raise ValidationError("give exactly one private key")
            key_path = _write(tmp, "key.pem", keys[0])
            key_pub = subprocess.run(["openssl", "pkey", "-in", key_path, "-pubout"], capture_output=True, text=True)
            if key_pub.returncode != 0:
                raise ValidationError("the private key could not be read (encrypted keys are not supported)")
            if key_pub.stdout != openssl("x509", "-noout", "-pubkey", data=leaf):
                raise ValidationError("the private key does not belong to this certificate")
            password = secrets.token_urlsafe(15)
            p12 = os.path.join(tmp, "out.p12")
            export_p12(leaf_path, key_path, [_write(tmp, "chain.pem", chain)] if chain else [],
                       out["name"], password, p12)
            with open(p12, "rb") as f:
                out.update(p12_b64=base64.b64encode(f.read()).decode(), p12_password=password)
    write_audit(actor, "PKI_CONVERT", f"subject={info['subject']} serial={info['serial']}"
                                      f"{' with key -> p12 (key not kept)' if out['p12_b64'] else ''}", source)
    return out
