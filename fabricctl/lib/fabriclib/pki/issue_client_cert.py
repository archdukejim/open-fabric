import os
import re
import secrets

from fabriclib.common.errors import ValidationError
from fabriclib.pki.export_p12 import export_p12
from fabriclib.pki.mint_offline_cert import mint_offline_cert

USER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@-]{0,63}$")


def issue_client_cert(v, user, out_dir, owner=(0, 0), days=365):
    """Issue a web UI client certificate for `user` (CN = the Keycloak
    username; the web UI refuses a login whose certificate CN differs).

    Writes <out_dir>/<user>.p12 (0600, owned by `owner`), protected by a
    generated password. The private key exists only inside the .p12.
    Returns (p12_path, password)."""
    if not USER_RE.match(user):
        raise ValidationError(f"invalid username for a client certificate: {user!r}")
    crt, key = mint_offline_cert(v, user, days=days, kty="RSA", size=3072)
    certs = os.path.join(v["deploy_base_dir"], "stepca", "data", "certs")
    p12 = os.path.join(out_dir, f"{user}.p12")
    password = secrets.token_urlsafe(18)
    try:
        export_p12(crt, key, [os.path.join(certs, "intermediate_ca.crt"), os.path.join(certs, "root_ca.crt")],
                   f"{user} (fabric)", password, p12)
    finally:
        for path in (crt, key):
            if os.path.exists(path):
                os.remove(path)
    os.chown(p12, *owner)
    return p12, password
