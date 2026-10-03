import os
import re
import secrets

from fabriclib.common.errors import ValidationError
from fabriclib.pki.export_p12 import export_p12
from fabriclib.pki.mint_offline_cert import mint_offline_cert

USER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@-]{0,63}$")


def issue_client_cert(v, user, out_dir, owner=(0, 0), days=365):
    """Purpose: Issue a web UI client certificate for a user as a password-protected .p12.
    Inputs:  v — fabric vars (CA and artifacts); user — username matching ^[A-Za-z0-9][A-Za-z0-9._@-]{0,63}$,
             becomes the CN; out_dir — existing directory; owner — (uid, gid) of the .p12, default root;
             days — validity, default 365.
    Returns: (p12_path "<out_dir>/<user>.p12", password): RSA 3072 key, chain intermediate + root,
             generated password (token_urlsafe(18)).
    Fails:   ValidationError "invalid username for a client certificate: ..."; mint_offline_cert /
             run_step's ValidationError; subprocess.CalledProcessError from export_p12; OSError (out_dir
             missing, chown).
    Feeds:   hand_out_client_cert; setup/create_admin.py run.
    Notes:   CN = the Keycloak username: the web UI refuses a login whose certificate CN differs. The key
             exists only inside the .p12; the minted crt/key artifacts are removed even on failure.
    """
    if not USER_RE.match(user):
        raise ValidationError(f"invalid username for a client certificate: {user!r}")
    crt, key = mint_offline_cert(v, user, days=days, kty="RSA", size=3072)
    certs = os.path.join(v["deploy_base_dir"], "stepca", "data", "certs")
    p12 = os.path.join(out_dir, f"{user}.p12")
    password = secrets.token_urlsafe(18)
    try:
        parents = os.path.join(certs, "ca_parents.crt")         # a nested site's parent CAs (empty otherwise)
        chain = [os.path.join(certs, "intermediate_ca.crt")] + ([parents] if os.path.exists(parents)
                                                                and os.path.getsize(parents) else [])
        export_p12(crt, key, chain + [os.path.join(certs, "root_ca.crt")],
                   f"{user} (fabric)", password, p12)
    finally:
        for path in (crt, key):
            if os.path.exists(path):
                os.remove(path)
    os.chown(p12, *owner)
    return p12, password
