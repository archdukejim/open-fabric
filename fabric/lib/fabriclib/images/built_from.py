import json
import subprocess


def built_from(image):
    """The base a locally built fabric image was built FROM (its
    org.fabric.base label), "" if the image has no label, None if the image
    does not exist."""
    try:
        res = subprocess.run(["docker", "image", "inspect", image], capture_output=True, text=True)
    except FileNotFoundError:           # no Docker (rendering only)
        return None
    if res.returncode != 0:
        return None
    labels = (json.loads(res.stdout)[0].get("Config") or {}).get("Labels") or {}
    return labels.get("org.fabric.base", "")
