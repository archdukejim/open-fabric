import os
import subprocess
import tempfile

from fabriclib.common.errors import ValidationError
from fabriclib.pki.common.describe_cert import describe_cert
from fabriclib.pki.common.openssl import openssl
from fabriclib.pki.common.to_pem import to_pem
from fabriclib.pki.make_site_ca_request import CSR, KEY


def stage_site_ca(work_dir, cert, root, root_sha256=""):
    """Purpose: On a joining site: check the root site's answer to make_site_ca_request and lay it out for
             Step-CA's bring-your-own-CA path (setup step `pki`, init_pki with byoc).
    Inputs:  work_dir — the directory make_site_ca_request used (holds site_ca_key and site_ca.csr); cert —
             PEM of the signed site intermediate; root — PEM of the root; root_sha256 — the root's SHA-256
             fingerprint the invitation pinned ("AA:BB:..."; empty skips the pin).
    Returns: vars for setup: {"byoc": True, "ca_crt_path": <work_dir>/root_ca.crt, "ica_crt_path":
             <work_dir>/site_ca.crt, "ica_key_path": <work_dir>/site_ca_key}; both certificates written 0644.
    Fails:   ValidationError "give exactly one certificate" (cert or root); "the root's fingerprint is not the
             one in the invitation"; "the root is not a self-signed CA"; "the site certificate does not chain
             to the root"; "the site certificate is not a path-length-0 CA"; "the site certificate is not for
             this site's key"; "no key/request in <work_dir>: make the request first"; to_pem's messages.
    Feeds:   setup --join (federation M3), before the `pki` step.
    """
    key, csr = os.path.join(work_dir, KEY), os.path.join(work_dir, CSR)
    if not (os.path.isfile(key) and os.path.isfile(csr)):
        raise ValidationError(f"no key/request in {work_dir}: make the request first")
    certs, roots = to_pem(cert, "cert"), to_pem(root, "cert")
    if len(certs) != 1 or len(roots) != 1:
        raise ValidationError("give exactly one certificate for the site CA and one for the root")
    cert, root = certs[0], roots[0]
    root_info = describe_cert(root)
    if root_sha256 and root_info["sha256"].upper() != root_sha256.upper():
        raise ValidationError("the root's fingerprint is not the one in the invitation")
    if not root_info["is_ca"] or root_info["subject"] != root_info["issuer"]:
        raise ValidationError("the root is not a self-signed CA")
    with tempfile.NamedTemporaryFile("w", suffix=".crt") as f:
        f.write(root)
        f.flush()
        if subprocess.run(["openssl", "verify", "-CAfile", f.name], input=cert, capture_output=True,
                          text=True).returncode != 0:
            raise ValidationError("the site certificate does not chain to the root")
    if "CA:TRUE, pathlen:0" not in openssl("x509", "-noout", "-text", data=cert):
        raise ValidationError("the site certificate is not a path-length-0 CA")
    with open(csr) as f:
        want = openssl("req", "-noout", "-pubkey", data=f.read())
    if openssl("x509", "-noout", "-pubkey", data=cert) != want:
        raise ValidationError("the site certificate is not for this site's key")
    paths = {"ca_crt_path": os.path.join(work_dir, "root_ca.crt"), "ica_crt_path": os.path.join(work_dir, "site_ca.crt")}
    for name, pem in (("ca_crt_path", root), ("ica_crt_path", cert)):
        with open(paths[name], "w") as f:
            f.write(pem)
        os.chmod(paths[name], 0o644)
    return {"byoc": True, **paths, "ica_key_path": key}
