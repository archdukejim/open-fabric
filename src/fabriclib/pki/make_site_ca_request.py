import os

from fabriclib.common.errors import ValidationError
from fabriclib.federation.constants import SITE_NAME_RE
from fabriclib.pki.common.run_step import run_step

KEY, CSR = "site_ca_key", "site_ca.csr"


def make_site_ca_request(v, site_name, password, work_dir):
    """Purpose: On a site that is joining: make the key of its intermediate CA and a certificate signing
             request for the root site to sign (sign_site_ca). The key never leaves this host.
    Inputs:  v — fabric vars: service_users.step.uid / .gid, image_stepca; site_name — SITE_NAME_RE;
             password — this site's ca_password (the key is encrypted with it, as `step ca init` does, so
             Step-CA opens it with its usual password file); work_dir — where the key and request are kept
             (created 0700, owned by the step user).
    Returns: {"csr": PEM str, CN "<site_name> Intermediate CA", "key_path": <work_dir>/site_ca_key (EC P-256,
             encrypted, 0600), "csr_path": <work_dir>/site_ca.csr}. A key and request already in work_dir are
             returned as they are, so a retried join keeps its key.
    Fails:   ValidationError "invalid site name: ..."; "the CA password is missing"; "step-ca refused: ..."
             (run_step); OSError (PermissionError when not root).
    Feeds:   setup --join (federation M3), then stage_site_ca with the root site's answer.
    Notes:   the password reaches step through a 0600 file in work_dir, removed afterwards, never argv.
    """
    if not SITE_NAME_RE.match(str(site_name)):
        raise ValidationError(f"invalid site name: {site_name!r} (one host-name label: a-z, 0-9, -)")
    if not password:
        raise ValidationError("the CA password is missing")
    uid, gid = (int(v["service_users"]["step"][k]) for k in ("uid", "gid"))
    os.makedirs(work_dir, mode=0o700, exist_ok=True)
    os.chmod(work_dir, 0o700)
    os.chown(work_dir, uid, gid)
    key, csr = os.path.join(work_dir, KEY), os.path.join(work_dir, CSR)
    if not (os.path.exists(key) and os.path.exists(csr)):
        for p in (key, csr):
            if os.path.exists(p):
                os.remove(p)
        pw = os.path.join(work_dir, ".password")
        fd = os.open(pw, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w") as f:
            f.write(password)
        os.chown(pw, uid, gid)
        try:
            run_step(v, ["certificate", "create", f"{site_name} Intermediate CA", f"/home/step/{CSR}",
                         f"/home/step/{KEY}", "--csr", "--kty", "EC", "--curve", "P-256",
                         "--password-file", "/home/step/.password"], home=work_dir)
        finally:
            os.remove(pw)
    os.chmod(key, 0o600)
    with open(csr) as f:
        return {"csr": f.read(), "key_path": key, "csr_path": csr}
