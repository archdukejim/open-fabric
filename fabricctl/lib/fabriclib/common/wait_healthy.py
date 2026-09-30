import subprocess
import time


def wait_healthy(container, timeout=300, interval=3):
    """Wait for a container's Docker healthcheck to report healthy.
    Returns (True, "healthy") or (False, reason)."""
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
