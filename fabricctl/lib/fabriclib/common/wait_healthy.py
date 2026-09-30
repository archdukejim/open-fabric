import subprocess
import time


def wait_healthy(container, timeout=300, interval=3):
    """Purpose: wait for a container's Docker healthcheck to report healthy.
    Inputs:  container — str, container name; timeout — seconds, default 300; interval — seconds between polls,
             default 3. Polls `docker inspect`.
    Returns: (True, "healthy"), or (False, reason): "unhealthy", "container exited|dead", or
             "timed out (<last health status>)".
    Fails:   never raises for a missing or unhealthy container (reported in the tuple); FileNotFoundError if the
             docker command is missing.
    Feeds:   setup/start_unit.py, setup/start_bootstrap.py.
    Notes:   a container without a healthcheck never reports healthy and runs into the timeout."""
    deadline = time.time() + timeout
    status = "missing"
    while time.time() < deadline:
        res = subprocess.run(["docker", "inspect", "-f", "{{.State.Status}} {{.State.Health.Status}}", container],
                             capture_output=True, text=True)
        if res.returncode == 0:
            state, _, status = res.stdout.strip().partition(" ")
            if status == "healthy":
                return True, "healthy"
            if status == "unhealthy":
                return False, "unhealthy"
            if state in ("exited", "dead"):
                return False, f"container {state}"
        time.sleep(interval)
    return False, f"timed out ({status})"
