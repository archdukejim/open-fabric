import shutil
import subprocess


def docker_ready():
    """Purpose: whether Docker Engine, compose v2 and buildx are installed and answer.
    Inputs:  none (runs `docker version`, `docker compose version`, `docker buildx version`).
    Returns: True only if docker is on PATH and all three exit 0.
    Fails:   never.
    Feeds:   setup/condition_host, consent/plan_packages."""
    return bool(shutil.which("docker")) and all(
        subprocess.run(cmd, capture_output=True).returncode == 0
        for cmd in (["docker", "version"], ["docker", "compose", "version"], ["docker", "buildx", "version"]))
