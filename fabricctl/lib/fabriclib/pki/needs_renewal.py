import os
import re
import subprocess

RENEW_BEFORE_SECONDS = 30 * 24 * 3600


def needs_renewal(cert_path, names, ca_certs=None):
    """Purpose: Decide whether a certificate on disk must be (re)issued.
    Inputs:  cert_path — PEM file; names — names that must be DNS or IP SANs ([] = no name check);
             ca_certs — optional (root_path, intermediate_path) the certificate must verify against.
    Returns: True if the file is missing, expires within 30 days (or cannot be read), does not verify
             against ca_certs, or lacks one of names; else False.
    Fails:   never for a bad certificate (openssl failures read as "renew"); FileNotFoundError only if
             openssl is not installed.
    Feeds:   setup/create_admin.py run, setup/mint_extra_certs.py mint_extra_certs,
             setup/mint_service_certs.py run.
    Notes:   the CA check catches a file left from an install whose CA has since been replaced.
    """
    if not os.path.exists(cert_path):
        return True
    if subprocess.run(["openssl", "x509", "-in", cert_path, "-noout", "-checkend", str(RENEW_BEFORE_SECONDS)],
                      capture_output=True).returncode != 0:
        return True
    if ca_certs:
        root, intermediate = ca_certs
        if subprocess.run(["openssl", "verify", "-CAfile", root, "-untrusted", intermediate, cert_path],
                          capture_output=True).returncode != 0:
            return True
    text = subprocess.run(["openssl", "x509", "-in", cert_path, "-noout", "-ext", "subjectAltName"],
                          capture_output=True, text=True).stdout
    have = set(re.findall(r"(?:DNS|IP Address):([^,\s]+)", text))
    return not set(names) <= have
