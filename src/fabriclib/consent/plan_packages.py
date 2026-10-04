from fabriclib.setup.common.docker_ready import docker_ready
from fabriclib.setup.common.missing_packages import missing_packages

# Only what the host itself runs; LDAP tools live in the dirsrv container.
HOST_PACKAGES = ["openssl", "ca-certificates", "curl", "ufw", "iptables", "dnsutils",
                 "python3-yaml", "python3-jinja2", "python3-bcrypt", "chrony"]
# Docker from the Ubuntu archive (universe): no extra apt source, updated with the release and carried across
# `do-release-upgrade`, which disables third-party sources (owner decision 2026-10-02).
DOCKER_PACKAGES = ["docker.io", "docker-compose-v2", "docker-buildx"]


def plan_packages():
    """Purpose: the apt packages setup installs (manual 2.7.1.3 `packages`), all from the host's own
             apt sources — fabric adds none.
    Inputs:  none (asks dpkg and docker).
    Returns: {"host": [missing HOST_PACKAGES], "docker": DOCKER_PACKAGES when Docker (with compose v2 and buildx)
             does not answer, else [], "text": [one "apt: install <pkg>" per package]}.
    Fails:   FileNotFoundError without dpkg-query.
    Feeds:   consent/plan_host_changes, setup/condition_host."""
    host = missing_packages(HOST_PACKAGES)
    docker = [] if docker_ready() else DOCKER_PACKAGES
    return {"host": host, "docker": docker, "text": [f"apt: install {p}" for p in host + docker]}
