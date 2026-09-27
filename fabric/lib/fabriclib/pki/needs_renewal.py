import os
import re
import subprocess

RENEW_BEFORE_SECONDS = 30 * 24 * 3600


def needs_renewal(cert_path, names):
    """True if the certificate is missing, expires within 30 days, or does
    not cover every name in `names` (DNS or IP SANs)."""
    if not os.path.exists(cert_path):
        return True
    if subprocess.run(["openssl", "x509", "-in", cert_path, "-noout", "-checkend", str(RENEW_BEFORE_SECONDS)],
                      capture_output=True).returncode != 0:
        return True
    text = subprocess.run(["openssl", "x509", "-in", cert_path, "-noout", "-ext", "subjectAltName"],
                          capture_output=True, text=True).stdout
    have = set(re.findall(r"(?:DNS|IP Address):([^,\s]+)", text))
    return not set(names) <= have
