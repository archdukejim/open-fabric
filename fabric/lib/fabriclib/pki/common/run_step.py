import os
import subprocess

from fabriclib.common.errors import ValidationError


def run_step(v, args):
    """Run the `step` CLI from the pinned Step-CA image as the step user,
    with the CA's data directory at /home/step (its keys never leave the
    host). Returns stdout; a failure raises ValidationError."""
    data = os.path.join(v["deploy_base_dir"], "stepca", "data")
    uid, gid = (int(v["service_users"]["step"][k]) for k in ("uid", "gid"))
    res = subprocess.run(["docker", "run", "--rm", "--network", "none", "-v", f"{data}:/home/step",
                          "--user", f"{uid}:{gid}", "--entrypoint", "/usr/local/bin/step", v["image_stepca"], *args],
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise ValidationError(f"step-ca refused: {(res.stderr or res.stdout).strip()[-300:]}")
    return res.stdout
