import json
import subprocess


def built_from(image, label="org.fabric.base"):
    """Purpose: the base a locally built fabric image was built FROM, read from a label on the image.
    Inputs:  image — str, local image name (e.g. "fabric/bind9:local"); label — str, default "org.fabric.base"
             (needs_rebuild also asks "org.fabric.kea" for the pinned Kea version). Runs `docker image inspect`.
    Returns: str label value; "" if the image has no such label; None if the image does not exist, the inspect
             fails, or Docker is not installed (render-only runs).
    Fails:   json.JSONDecodeError or IndexError only if docker prints unexpected output.
    Feeds:   needs_rebuild, running_image."""
    try:
        res = subprocess.run(["docker", "image", "inspect", image], capture_output=True, text=True)
    except FileNotFoundError:           # no Docker (rendering only)
        return None
    if res.returncode != 0:
        return None
    labels = (json.loads(res.stdout)[0].get("Config") or {}).get("Labels") or {}
    return labels.get(label, "")
