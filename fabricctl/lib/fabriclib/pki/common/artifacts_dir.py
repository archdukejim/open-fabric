import os


def artifacts_dir(v):
    """Purpose: The step user's scratch directory for minted and signed files, created if missing.
             The step CLI sees it as /home/step/artifacts.
    Inputs:  v — fabric vars (dict): deploy_base_dir, service_users.step.uid / .gid.
    Returns: path (str) <deploy_base_dir>/stepca/data/artifacts, mode 0750 when created, chowned to the
             step user on every call.
    Fails:   KeyError if deploy_base_dir or service_users.step is missing; OSError (PermissionError) from
             makedirs/chown when not run as root.
    Feeds:   mint_offline_cert, sign_csr, sign_site_ca.
    """
    uid, gid = (int(v["service_users"]["step"][k]) for k in ("uid", "gid"))
    path = os.path.join(v["deploy_base_dir"], "stepca", "data", "artifacts")
    os.makedirs(path, mode=0o750, exist_ok=True)
    os.chown(path, uid, gid)
    return path
