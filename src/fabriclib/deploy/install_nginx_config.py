import os

from fabriclib.common.copy_if_changed import copy_if_changed
from fabriclib.common.ensure_dir import ensure_dir
from fabriclib.common.service_user import service_user


def install_nginx_config(paths, final_vars):
    """Purpose: nginx's configuration, and fabric.target (the unit grouping every fabric unit: `systemctl
             start|stop|restart fabric.target`).
    Inputs:  paths — deploy_paths() (base, jinja, render); final_vars — rendered settings (service_users.nginx).
    Returns: {"nginx": True if nginx.conf changed (reload), "daemon_reload": True if fabric.target changed}; a
             placeholder conf.d/client-crl.inc when there is none yet.
    Fails:   OSError from creating the folder or copying.
    Feeds:   apply_deployment."""
    uid, gid = service_user(final_vars, "nginx")
    ensure_dir(os.path.join(paths["base"], "nginx/config"), 0o755, uid, gid)
    target = copy_if_changed(os.path.join(paths["jinja"], "systemd", "fabric.target"),
                             "/etc/systemd/system/fabric.target", 0o644)
    # the web console's CRL check (pki/publish_crl writes it once the CA exists): nginx needs the file to start
    crl_inc = os.path.join(paths["base"], "nginx/config/conf.d/client-crl.inc")
    if not os.path.exists(crl_inc):
        ensure_dir(os.path.dirname(crl_inc), 0o755, uid, gid)
        with open(crl_inc, "w") as f:
            f.write("# no CRL yet: written by fabriclib/pki/publish_crl.py (manual 2.1.5.10)\n")
        os.chown(crl_inc, uid, gid)
    nginx = copy_if_changed(os.path.join(paths["render"], "nginx/nginx.conf"),
                            os.path.join(paths["base"], "nginx/config/nginx.conf"), 0o644, uid, gid)
    return {"nginx": nginx, "daemon_reload": target}
