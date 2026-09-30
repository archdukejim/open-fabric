import os

from fabriclib.common.sudo_owner import sudo_owner
from fabriclib.pki.issue_client_cert import issue_client_cert


def hand_out_client_cert(v, user, days=365):
    """`fabricctl client-cert <user>`: issue a web UI client certificate into
    ~/fabric-admin of the account that ran sudo. Returns (p12_path, password);
    the caller shows the password once. The user must be in the web UI admin
    group in LDAP to get past the login."""
    _, home, uid, gid = sudo_owner()
    folder = os.path.join(home, "fabric-admin")
    os.makedirs(folder, mode=0o700, exist_ok=True)
    os.chown(folder, uid, gid)
    return issue_client_cert(v, user, folder, owner=(uid, gid), days=days)
