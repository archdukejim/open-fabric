import os
import subprocess

import yaml

from fabriclib.common.copy_if_changed import copy_if_changed
from fabriclib.common.copy_tree_with_perms import copy_tree_with_perms
from fabriclib.common.ensure_dir import ensure_dir
from fabriclib.common.service_user import service_user
from fabriclib.deploy.compose_builds import compose_builds
from fabriclib.images.needs_rebuild import needs_rebuild

# a service's folder -> the service user owning it (others: the folder's own name)
OWNER = {"bind9": "bind", "stepca": "step", "dirsrv": "ldap"}


def _present(compose_file):
    """Purpose: whether every image a rendered compose file names is already on this host.
    Inputs:  compose_file — str, path of a rendered docker-compose.yml. Asks `docker image inspect`.
    Returns: bool; False if Docker is missing (rendering only) or an image is not there.
    Fails:   OSError if the file is unreadable; yaml.YAMLError on invalid YAML.
    Feeds:   install_service_units."""
    with open(compose_file) as f:
        services = (yaml.safe_load(f) or {}).get("services") or {}
    images = sorted({svc["image"] for svc in services.values() if (svc or {}).get("image")})
    try:
        return subprocess.run(["docker", "image", "inspect", *images], capture_output=True).returncode == 0
    except FileNotFoundError:
        return False


def install_service_units(paths, final_vars, units):
    """Purpose: install each service's compose file, local image build context and systemd wrapper.
    Inputs:  paths — deploy_paths() (base, fabric_dir, jinja, render); final_vars — rendered settings
             (service_users, install_keycloak, install_ldap); units — service_units().
    Returns: {"restart": set of units whose compose file, image or unit changed, "rebuild": set of folders whose
             image must be prepared: a local image to build (its build context changed, or its base is not the
             pinned one) or fabric's published image to pull (not on the host yet),
             "daemon_reload": bool}.
    Fails:   OSError from copying or setting owners.
    Feeds:   apply_deployment.
    Notes:   every service gets its <base>/<folder> (owned by its service user) except Keycloak/Postgres and 389-DS
             when they are off; only rendered (enabled) services get files. The web UI's build context also carries
             its app code (fabric's lib/webui)."""
    base, out = paths["base"], paths["render"]
    restart, rebuild, reload_ = set(), set(), False
    for u in units:
        folder, name = u["folder"], u["service"]
        if folder in ("keycloak", "postgres") and not final_vars.get("install_keycloak"):
            continue
        if folder == "dirsrv" and not final_vars.get("install_ldap"):
            continue
        uid, gid = service_user(final_vars, OWNER.get(folder, folder))
        svc_dir = os.path.join(base, folder)
        ensure_dir(svc_dir, 0o750, uid, gid)
        src_dc = os.path.join(out, folder, "docker-compose.yml")
        changed = os.path.exists(src_dc) and copy_if_changed(src_dc, os.path.join(svc_dir, "docker-compose.yml"),
                                                              0o640, uid, gid)
        build_src = os.path.join(paths["jinja"], folder, "build")
        if os.path.isdir(build_src) and os.path.exists(src_dc):
            build_dst = os.path.join(svc_dir, "build")
            context_changed = copy_tree_with_perms(build_src, build_dst, 0, 0, 0o644, 0o755)
            if folder == "webui":
                context_changed |= copy_tree_with_perms(os.path.join(paths["fabric_dir"], "lib", "webui"),
                                                        os.path.join(build_dst, "app"), 0, 0, 0o644, 0o755)
            if compose_builds(src_dc):
                if context_changed or needs_rebuild(src_dc):
                    rebuild.add(folder)
                    changed = True
            elif not _present(src_dc):      # fabric's published image (manual 2.6.3.3): pulled, not built
                rebuild.add(folder)
        src_unit = os.path.join(out, "systemd", f"{name}.service")
        if os.path.exists(src_unit) and copy_if_changed(src_unit, f"/etc/systemd/system/{name}.service", 0o644):
            changed = reload_ = True
        if changed:
            restart.add(name)
    return {"restart": restart, "rebuild": rebuild, "daemon_reload": reload_}
