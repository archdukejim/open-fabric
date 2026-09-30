import os
import re
import subprocess

RENEW_BEFORE_SECONDS = 30 * 24 * 3600


def needs_renewal(cert_path, names, ca_certs=None):
    """True if the certificate is missing, expires within 30 days, does not
    cover every name in `names` (DNS or IP SANs), or — given ca_certs
    (root, intermediate) — was not issued by that CA (e.g. a file left over
    from an install whose CA has since been replaced)."""
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
