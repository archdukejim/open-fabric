import os


def artifacts_dir(v):
    """<base>/stepca/data/artifacts (seen as /home/step/artifacts by the step
    CLI): scratch space owned by the step user, 0750."""
    uid, gid = (int(v["service_users"]["step"][k]) for k in ("uid", "gid"))
    path = os.path.join(v["deploy_base_dir"], "stepca", "data", "artifacts")
    os.makedirs(path, mode=0o750, exist_ok=True)
    os.chown(path, uid, gid)
    return path
