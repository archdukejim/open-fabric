import subprocess

from fabriclib.images.built_from import built_from


def running_image(service):
    """What a service runs now: for a pulled image the ref its container was
    created from; for a local build the base it was built FROM. None if the
    container (or local image) does not exist."""
    if service["build"]:
        return built_from(service["build"]) or None
    res = subprocess.run(["docker", "inspect", "-f", "{{.Config.Image}}", service["container"]],
                         capture_output=True, text=True)
    return res.stdout.strip() if res.returncode == 0 else None
