import os

from fabriclib.common.sudo_owner import sudo_owner
from fabriclib.pki.issue_client_cert import issue_client_cert


def hand_out_client_cert(v, user, days=365):
    """Purpose: `fabricctl client-cert <user>`: issue a web UI client certificate into ~/fabric-admin of
             the account that ran sudo.
    Inputs:  v — fabric vars (CA, via issue_client_cert); user — Keycloak username (USER_RE in
             issue_client_cert); days — validity, default 365 (no cap here). Reads SUDO_USER (sudo_owner).
    Returns: (p12_path, password); the CLI shows the password once.
    Fails:   ValidationError from issue_client_cert (invalid username) or mint_offline_cert / run_step
             ("step-ca refused: ..."); subprocess.CalledProcessError from export_p12; OSError from
             makedirs / chown.
    Feeds:   fabriclib/cli.py (fabricctl client-cert).
    Notes:   ~/fabric-admin is created 0700 and owned by the sudo user. The certificate alone grants
             nothing: the user must also pass the Keycloak login (e.g. be in the web UI admin group).
    """
    _, home, uid, gid = sudo_owner()
    folder = os.path.join(home, "fabric-admin")
    os.makedirs(folder, mode=0o700, exist_ok=True)
    os.chown(folder, uid, gid)
    return issue_client_cert(v, user, folder, owner=(uid, gid), days=days)
