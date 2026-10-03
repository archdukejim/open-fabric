import os
import shutil
import subprocess
import tempfile

from fabriclib.common.errors import ValidationError

PROGRAMS = {"kea-dhcp4.conf": "/usr/sbin/kea-dhcp4", "kea-dhcp-ddns.conf": "/usr/sbin/kea-dhcp-ddns"}


def check_kea_config(image, name, text):
    """Purpose: have Kea itself check a configuration before fabric installs it (`kea-dhcp4 -t`, design
             dhcp-management.md §3): a file Kea would refuse is never put in place.
    Inputs:  image — fabric's Kea image (vars image_kea); name — "kea-dhcp4.conf" or "kea-dhcp-ddns.conf";
             text — the rendered configuration.
    Returns: True when Kea accepted it; None when it could not be checked (no Docker, or the image is not built
             yet — a first install: the service start then reports any error).
    Fails:   ValidationError with Kea's own message when it refuses the file; subprocess.TimeoutExpired (60 s).
    Feeds:   dhcp/deploy_kea.
    Notes:   runs in a throwaway container on the host network (Kea checks the served interfaces exist; `-t` opens
             no socket), with no capabilities and a read-only root; the file is
             mounted read-only."""
    if not shutil.which("docker") or subprocess.run(["docker", "image", "inspect", image],
                                                    capture_output=True).returncode != 0:
        return None
    with tempfile.TemporaryDirectory() as tmp:
        os.chmod(tmp, 0o755)
        path = os.path.join(tmp, name)
        with open(path, "w") as f:
            f.write(text)
        os.chmod(path, 0o644)
        res = subprocess.run(["docker", "run", "--rm", "--network", "host", "--cap-drop", "ALL", "--read-only",
                              "--security-opt", "no-new-privileges:true", "--tmpfs", "/run/kea", "--tmpfs",
                              "/var/run/kea", "--tmpfs", "/tmp", "-v", f"{tmp}:/check:ro", "--entrypoint",
                              PROGRAMS[name], image, "-t", f"/check/{name}"],
                             capture_output=True, text=True, timeout=60)
    if res.returncode != 0:
        lines = [l for l in (res.stdout + res.stderr).splitlines() if "ERROR" in l or "error" in l.lower()]
        raise ValidationError(f"Kea refused the new {name}: " + (" | ".join(lines[-3:]) or res.stderr[-400:])
                              + " — nothing was changed")
    return True
