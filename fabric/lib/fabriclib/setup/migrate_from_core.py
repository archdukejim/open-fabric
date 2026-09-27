import datetime
import os
import re
import shutil
import subprocess

from fabriclib.common.console import info, ok

SERVICES = ["webui", "nginx", "keycloak", "postgres", "ldap", "stepca", "bind9"]


def run(ctx):
    """Move a pre-fabric (core-template) install in place. No-op when there
    is no <base>/core or <base>/fabric already exists.

      <base>/core                   -> <base>/fabric
      config/core-secrets.yml       -> config/fabric-secrets.yml
      vars key core_subnet          -> fabric_subnet
      docker network core_net       -> removed (fabric_net is created later)
      /usr/local/bin/core-mgr       -> removed (fabricctl + alias installed later)
      resolved.conf.d/core-dns.conf -> removed (fabric-dns.conf written later)
    Service data (/opt/nginx, /opt/bind9, ...) is not touched."""
    old = ctx.path("core")
    if not os.path.isdir(old) or os.path.exists(ctx.target_dir):
        ok("no core-template install to migrate")
        return

    info("stopping services (the Docker network is replaced)")
    for svc in SERVICES:
        subprocess.run(["systemctl", "stop", svc], capture_output=True)

    shutil.move(old, ctx.target_dir)
    ok(f"moved {old} -> {ctx.target_dir}")

    old_secrets = os.path.join(ctx.config_dir, "core-secrets.yml")
    if os.path.exists(old_secrets) and not os.path.exists(ctx.secrets_file):
        os.rename(old_secrets, ctx.secrets_file)
        ok("renamed core-secrets.yml -> fabric-secrets.yml")

    if os.path.exists(ctx.vars_file):
        with open(ctx.vars_file) as f:
            text = f.read()
        new = re.sub(r"^core_subnet:", "fabric_subnet:", text, flags=re.MULTILINE)
        if new != text:
            with open(ctx.vars_file, "w") as f:
                f.write(new)
            ok("renamed vars key core_subnet -> fabric_subnet")

    res = subprocess.run(["docker", "network", "inspect", "core_net", "-f",
                          "{{range .Containers}}{{.Name}} {{end}}"], capture_output=True, text=True)
    if res.returncode == 0:
        for name in res.stdout.split():
            subprocess.run(["docker", "network", "disconnect", "-f", "core_net", name], capture_output=True)
        subprocess.run(["docker", "network", "rm", "core_net"], capture_output=True)
        ok("removed docker network core_net")

    for path in ("/usr/local/bin/core-mgr", "/etc/systemd/resolved.conf.d/core-dns.conf"):
        if os.path.exists(path):
            os.remove(path)

    os.makedirs(os.path.join(ctx.target_dir, "archive"), mode=0o700, exist_ok=True)
    with open(os.path.join(ctx.target_dir, "archive", "audit.log"), "a") as f:
        f.write(f"[{datetime.datetime.now().isoformat(timespec='seconds')}] migration core-template -> fabric\n")
    ok("core-template install migrated")
