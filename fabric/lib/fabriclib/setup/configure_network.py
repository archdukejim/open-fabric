import os
import subprocess

from fabriclib.common.console import ok

RESOLVED_DROPIN = "/etc/systemd/resolved.conf.d/fabric-dns.conf"


def run(ctx):
    """Docker network fabric_net (the services' private bridge) and, unless
    use_host_dns, point the host resolver at dns_server during bootstrap."""
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
        with open(RESOLVED_DROPIN, "w") as f:
            f.write(content)
        if os.path.islink("/etc/resolv.conf") or os.path.exists("/etc/resolv.conf"):
            os.remove("/etc/resolv.conf")
        os.symlink("/run/systemd/resolve/resolv.conf", "/etc/resolv.conf")
        subprocess.run(["systemctl", "restart", "systemd-resolved"], check=True)
    ok(f"host resolver uses {ctx.vars.get('dns_server')} (stub listener off, frees port 53)")
