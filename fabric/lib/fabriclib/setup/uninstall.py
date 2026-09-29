import glob
import os
import shutil
import subprocess

from fabriclib.common.console import info, ok, warn

UNITS = ["fabric-web", "webui", "fluentbit", "kea", "fabric-agent", "nginx", "openbao", "keycloak", "postgres", "ldap", "stepca", "bind9", "fabric-firewall"]
TARGET = "/etc/systemd/system/fabric.target"
CONTAINERS = ["fabric-web", "webui", "fluentbit", "kea-dhcp4", "kea-ddns", "nginx", "openbao", "keycloak", "postgres", "dirsrv", "step-ca", "bind9"]
DIRS = ["fabric", "nginx", "bind9", "stepca", "dirsrv", "keycloak", "postgres", "webui", "openbao", "fluentbit", "kea"]
LOCAL_IMAGES = ["fabric/bind9:local", "fabric/stepca:local", "fabric/dirsrv:local", "fabric/keycloak:local",
                "fabric/web:local", "fabric/webui:local", "fabric/kea:local"]


def uninstall(ctx):
    """Remove fabric from this host: units, containers, fabric_net, local
    images, data directories, service accounts, CA trust, the CLI.
    Only fabric's own objects are touched (no global Docker prune, no Docker
    restart); host firewall defaults stay as they are."""
    ctx.load_state()
    v = ctx.vars

    info("stopping and removing services")
    for unit in UNITS:
        subprocess.run(["systemctl", "disable", "--now", unit], capture_output=True)
        path = f"/etc/systemd/system/{unit}.service"
        if os.path.exists(path):
            os.remove(path)
    subprocess.run(["systemctl", "disable", "--now", "fabric.target"], capture_output=True)
    if os.path.exists(TARGET):
        os.remove(TARGET)
    subprocess.run(["systemctl", "daemon-reload"], capture_output=True)
    for c in CONTAINERS:
        subprocess.run(["docker", "rm", "-f", c], capture_output=True)
    subprocess.run(["docker", "network", "rm", "fabric_net"], capture_output=True)
    subprocess.run(["docker", "rmi", *LOCAL_IMAGES], capture_output=True)
    subprocess.run(["iptables", "-F", "DOCKER-USER"], capture_output=True)
    subprocess.run(["iptables", "-A", "DOCKER-USER", "-j", "RETURN"], capture_output=True)
    ok("services, containers, fabric_net and local images removed")

    for key in ("keycloak_data_dir", "postgres_data_dir"):
        path = v.get(key)
        if path and not path.startswith(ctx.deploy_base + os.sep) and os.path.isdir(path):
            shutil.rmtree(path)
            ok(f"removed {path}")
    extra = [k.get("name") for k in (v.get("tsig_keys") or []) if k.get("name")]
    for name in DIRS + extra:
        shutil.rmtree(ctx.path(name), ignore_errors=True)
    for path in glob.glob(ctx.path("acme_*")):
        shutil.rmtree(path, ignore_errors=True)
    ok(f"removed fabric directories under {ctx.deploy_base}")
    shutil.rmtree(v.get("openbao_runtime_dir") or "/run/fabric/openbao", ignore_errors=True)
    shutil.rmtree(v.get("openbao_admin_dir") or "/run/fabric/openbao-admin", ignore_errors=True)
    rules = v.get("openbao_udev_rules") or "/etc/udev/rules.d/90-fabric-unlock.rules"
    if os.path.exists(rules):                   # the unlock-device kill switch
        os.remove(rules)
        subprocess.run(["udevadm", "control", "--reload"], capture_output=True)
    key_dir = v.get("openbao_key_dir")
    if key_dir and os.path.isdir(key_dir):
        shutil.rmtree(key_dir)
        ok(f"removed the OpenBao seal key ({key_dir}): its vault data is gone too")

    for name in (v.get("service_users") or {}):
        if subprocess.run(["id", name], capture_output=True).returncode == 0:
            subprocess.run(["userdel", name], capture_output=True)
            subprocess.run(["groupdel", name], capture_output=True)
    ok("service accounts removed")

    for name in ("root-ca", "intermediate-ca"):          # written by pki/publish_ca_certs.py
        path = f"/usr/local/share/ca-certificates/fabric-{v.get('domain_file')}-{name}.crt"
        if v.get("domain_file") and os.path.exists(path):
            os.remove(path)
    subprocess.run(["update-ca-certificates", "--fresh"], capture_output=True)
    for path in ("/usr/local/bin/fabricctl", "/etc/systemd/resolved.conf.d/fabric-dns.conf"):
        if os.path.exists(path):
            os.remove(path)
    ok("CA removed from the host trust store; fabricctl removed")
    warn("ufw stays enabled with its default-deny policy; `ufw disable` if you no longer want it")
