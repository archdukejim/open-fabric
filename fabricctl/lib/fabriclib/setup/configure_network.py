import os
import subprocess

from fabriclib.common.console import ok
from fabriclib.consent.check_consent import check_consent
from fabriclib.consent.plan_resolver import plan_resolver

RESOLVED_DROPIN = "/etc/systemd/resolved.conf.d/fabric-dns.conf"


def run(ctx):
    """Purpose: create the Docker network fabric_net (the services' private bridge) and, when use_host_dns is
             false, point the host resolver at dns_server with the stub listener off (frees port 53).
    Inputs:  ctx — SetupContext: vars fabric_subnet (default 10.255.0.0/24), use_host_dns (default True),
             dns_server (default 8.8.8.8), config_dir (the `resolver` consent, asked before the first step).
    Returns: None; fabric_net exists (an existing one is not checked or changed). Without use_host_dns: the
             resolved drop-in RESOLVED_DROPIN is written and /etc/resolv.conf re-linked to systemd-resolved's
             file, restarting it — only when the drop-in changed.
    Fails:   SetupError when the resolver change was not approved; CalledProcessError from `docker network create` or `systemctl restart systemd-resolved`; OSError
             on the files.
    Feeds:   setup step `network`, run by run_setup via STEPS."""
    subnet = ctx.vars.get("fabric_subnet", "10.255.0.0/24")
    if subprocess.run(["docker", "network", "inspect", "fabric_net"], capture_output=True).returncode != 0:
        subprocess.run(["docker", "network", "create", "--subnet", subnet, "fabric_net"],
                       check=True, capture_output=True)
        ok(f"created docker network fabric_net ({subnet})")
    else:
        ok("docker network fabric_net exists")

    if ctx.vars.get("use_host_dns", True):
        ok("host resolver unchanged (use_host_dns)")
        return
    content = f"[Resolve]\nDNS={ctx.vars.get('dns_server', '8.8.8.8')}\nDNSStubListener=no\n"
    os.makedirs(os.path.dirname(RESOLVED_DROPIN), exist_ok=True)
    old = open(RESOLVED_DROPIN).read() if os.path.exists(RESOLVED_DROPIN) else None
    if old != content:
        check_consent(ctx.config_dir, "resolver", plan_resolver(ctx.vars))
        with open(RESOLVED_DROPIN, "w") as f:
            f.write(content)
        if os.path.islink("/etc/resolv.conf") or os.path.exists("/etc/resolv.conf"):
            os.remove("/etc/resolv.conf")
        os.symlink("/run/systemd/resolve/resolv.conf", "/etc/resolv.conf")
        subprocess.run(["systemctl", "restart", "systemd-resolved"], check=True)
    ok(f"host resolver uses {ctx.vars.get('dns_server')} (stub listener off, frees port 53)")
