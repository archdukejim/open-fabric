import subprocess

from fabriclib.common.wait_healthy import wait_healthy
from fabriclib.setup.errors import SetupError


def start_unit(unit, container, restart):
    """Enable a fabric unit (links it into multi-user.target and
    fabric.target), start or restart it, and wait for its container to be
    healthy. Returns "running", "started" or "restarted"."""
    subprocess.run(["systemctl", "enable", unit], check=True, capture_output=True)
    active = subprocess.run(["systemctl", "is-active", "--quiet", unit]).returncode == 0
    if active and not restart:
        return "running"
    subprocess.run(["systemctl", "restart" if active else "start", unit], check=True)
    healthy, why = wait_healthy(container, timeout=900)
    if not healthy:
        logs = subprocess.run(["docker", "logs", "--tail", "40", container], capture_output=True, text=True)
        raise SetupError(f"{container} did not become healthy ({why}):\n{logs.stdout}{logs.stderr}")
    return "restarted" if active else "started"
