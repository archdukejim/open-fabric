import os

from fabriclib.common.copy_if_changed import copy_if_changed
from fabriclib.common.ensure_dir import ensure_dir
from fabriclib.common.service_user import service_user


def install_webui_files(paths, final_vars):
    """Purpose: the web UI's folders and config, and fabric-agent's host unit.
    Inputs:  paths — deploy_paths() (base, render); final_vars — rendered settings (install_webui,
             service_users.webui and .nginx).
    Returns: {"webui": True if webui.json changed, "agent": True if the fabric-agent unit changed}; both False when
             the web UI is off.
    Fails:   OSError from creating folders or copying.
    Feeds:   apply_deployment.
    Notes:   run/ is the container's socket to nginx (webui:nginx), agent/ fabric-agent's socket (root:webui);
             webui.json is 0400 for the container user only."""
    if not final_vars.get("install_webui"):
        return {"webui": False, "agent": False}
    uid, gid = service_user(final_vars, "webui")
    nginx_gid = service_user(final_vars, "nginx")[1]
    base = os.path.join(paths["base"], "webui")
    ensure_dir(base, 0o755)
    ensure_dir(os.path.join(base, "config"), 0o750, 0, gid)
    ensure_dir(os.path.join(base, "run"), 0o750, uid, nginx_gid)
    ensure_dir(os.path.join(base, "agent"), 0o750, 0, gid)
    cfg = os.path.join(base, "config/webui.json")
    webui = copy_if_changed(os.path.join(paths["render"], "webui/webui.json"), cfg, 0o400, uid, gid)
    os.chown(cfg, uid, gid)
    os.chmod(cfg, 0o400)
    agent = copy_if_changed(os.path.join(paths["render"], "systemd/fabric-agent.service"),
                            "/etc/systemd/system/fabric-agent.service", 0o644)
    return {"webui": webui, "agent": agent}
