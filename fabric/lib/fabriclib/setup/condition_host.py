import os
import shutil
import subprocess
import time

from fabriclib.common.console import info, ok
from fabriclib.common.run import CommandError, run as sh
from fabriclib.setup.errors import SetupError

# Only what the host itself runs; LDAP tools live in the dirsrv container.
HOST_PACKAGES = ["openssl", "ca-certificates", "curl", "gnupg", "ufw", "iptables", "dnsutils",
                 "python3-yaml", "python3-jinja2"]
DOCKER_PACKAGES = ["docker-ce", "docker-ce-cli", "containerd.io", "docker-buildx-plugin", "docker-compose-plugin"]
APT_ENV = {**os.environ, "DEBIAN_FRONTEND": "noninteractive", "NEEDRESTART_MODE": "a"}


def _missing(pkgs):
    res = subprocess.run(["dpkg-query", "-W", "-f=${Package} ${Status}\\n", *pkgs], capture_output=True, text=True)
    installed = {l.split()[0] for l in res.stdout.splitlines() if l.endswith("install ok installed")}
    return [p for p in pkgs if p not in installed]


def _docker_ok():
    return all(subprocess.run(cmd, capture_output=True).returncode == 0
               for cmd in (["docker", "version"], ["docker", "compose", "version"], ["docker", "buildx", "version"]))


def _install_docker():
    """Docker's official apt repository (docker-ce + compose + buildx)."""
    rel = {}
    with open("/etc/os-release") as f:
        for line in f:
            k, _, v = line.strip().partition("=")
            rel[k] = v.strip('"')
    distro = rel.get("ID", "ubuntu")
    codename = rel.get("VERSION_CODENAME") or rel.get("UBUNTU_CODENAME")
    arch = sh(["dpkg", "--print-architecture"]).stdout.strip()
    os.makedirs("/etc/apt/keyrings", mode=0o755, exist_ok=True)
    sh(["curl", "-fsSL", "-o", "/etc/apt/keyrings/docker.asc", f"https://download.docker.com/linux/{distro}/gpg"])
    os.chmod("/etc/apt/keyrings/docker.asc", 0o644)
    with open("/etc/apt/sources.list.d/docker.list", "w") as f:
        f.write(f"deb [arch={arch} signed-by=/etc/apt/keyrings/docker.asc] "
                f"https://download.docker.com/linux/{distro} {codename} stable\n")
    sh(["apt-get", "update"], env=APT_ENV, timeout=900)
    sh(["apt-get", "install", "-y", "--no-install-recommends", *DOCKER_PACKAGES], env=APT_ENV, timeout=1800)


def run(ctx):
    """Host packages and Docker Engine (compose v2 + buildx), running and enabled."""
    missing = _missing(HOST_PACKAGES)
    if missing:
        if ctx.offline:
            raise SetupError(f"offline install but host packages are missing: {' '.join(missing)}")
        info(f"installing {' '.join(missing)}")
        sh(["apt-get", "update"], env=APT_ENV, timeout=900)
        try:
            sh(["apt-get", "install", "-y", "--no-install-recommends", *missing], env=APT_ENV, timeout=1800)
        except CommandError as e:
            raise SetupError(f"apt could not install {' '.join(missing)}: {str(e)[-600:]}\n"
                             "If apt reports unmet dependencies or held broken packages, the host's apt sources "
                             "are usually incomplete (e.g. missing <release>-updates, which the installed "
                             "libraries came from). Fix the sources, run `apt-get update`, then re-run setup.") from None
    ok("host packages present")

    if not (shutil.which("docker") and _docker_ok()):
        if ctx.offline:
            raise SetupError("offline install but Docker (with compose v2 and buildx) is not installed")
        info("installing Docker Engine from Docker's apt repository")
        _install_docker()
    sh(["systemctl", "enable", "--now", "docker"])
    for _ in range(12):
        if subprocess.run(["docker", "info"], capture_output=True).returncode == 0:
            break
        time.sleep(5)
    else:
        raise SetupError("Docker is installed but not responding (docker info)")
    ok(sh(["docker", "version", "-f", "Docker {{.Server.Version}}"]).stdout.strip()
       + ", " + sh(["docker", "compose", "version", "--short"]).stdout.strip().join(["compose ", ""]))
