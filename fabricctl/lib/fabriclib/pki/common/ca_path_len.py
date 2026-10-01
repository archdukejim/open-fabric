import re

from fabriclib.pki.common.openssl import openssl


def ca_path_len(pem):
    """Purpose: how many levels of CAs a CA certificate may still sign below it (its basicConstraints path length).
    Inputs:  pem — str, a PEM certificate (the first one is read).
    Returns: int path length; None for a CA without a limit; -1 when the certificate is not a CA.
    Fails:   ValidationError from openssl when the PEM cannot be parsed.
    Feeds:   sign_site_ca (what the signer may give), create_invitation (whether this install may nest),
             stage_site_ca, init_pki (report a brought-in root's depth)."""
    text = openssl("x509", "-noout", "-ext", "basicConstraints", data=pem)
    if "CA:TRUE" not in text:
        return -1
    m = re.search(r"pathlen:(\d+)", text)
    return int(m.group(1)) if m else None
