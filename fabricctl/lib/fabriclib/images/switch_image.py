import json
import os
import subprocess

from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.images.constants import STATE
from fabriclib.images.installed_services import installed_services
from fabriclib.setup import deploy_config
from fabriclib.setup.errors import SetupError
from fabriclib.setup.start_unit import start_unit


def _apply(ctx, var, ref, services):
    """Purpose: render and deploy with image var `var` set to `ref` (local images rebuild on the new base),
             then restart each service through its systemd unit and wait until it is healthy.
    Inputs:  ctx — SetupContext (ctx.vars is changed in place and persisted by deploy_config); var — str image var;
             ref — str image ref; services — list of SERVICES entries to restart, in order.
    Returns: None.
    Fails:   SetupError from start_unit when a container does not become healthy; subprocess.CalledProcessError
             from systemctl; anything deploy_config.run / deploy.py raises (SystemExit on a deploy failure).
    Feeds:   switch_image (update and its rollback)."""
    ctx.vars[var] = ref
    deploy_config.run(ctx)
    for s in services:
        start_unit(s["unit"], s["container"], restart=True)


def switch_image(ctx, var, target, actor="root", source="cli"):
    """Purpose: move every installed service using image var `var` to `target`, one at a time in dependency
             order, health-gated; restore the previous ref the same way if one does not come back healthy, and
             remember the previous ref for `images rollback`.
    Inputs:  ctx — SetupContext with vars; var — str image var (e.g. "image_debian"); target — str ref pinned by
             digest; actor, source — for the audit log. Writes STATE (/etc/fabric/images/state.json, 0600).
    Returns: list of service names moved; [] if none is installed or var is already target.
    Fails:   ValidationError if target is not pinned by digest, the pull fails (nothing touched), the update
             failed and was rolled back, or the rollback failed too. Only SetupError, SystemExit and
             CalledProcessError trigger the rollback; any other exception from _apply propagates with no rollback.
    Feeds:   update_images, rollback_image."""
    if "@sha256:" not in (target or ""):
        raise ValidationError(f"{target!r} is not pinned by digest")
    previous = ctx.vars.get(var)
    services = [s for s in installed_services(ctx) if s["var"] == var]
    if not services or previous == target:
        return []
    pull = subprocess.run(["docker", "pull", "-q", target], capture_output=True, text=True, timeout=1800)
    if pull.returncode != 0:            # nothing touched yet
        raise ValidationError(f"could not download {target}: {(pull.stderr or pull.stdout).strip()[-300:]}")
    try:
        _apply(ctx, var, target, services)
    except (SetupError, SystemExit, subprocess.CalledProcessError) as exc:
        write_audit(actor, "IMAGE_UPDATE", f"{var} {previous} -> {target} FAILED, rolling back: {exc}"[:600], source)
        try:
            _apply(ctx, var, previous, services)
        except (SetupError, SystemExit, subprocess.CalledProcessError) as again:
            raise ValidationError(f"{var}: the update failed and so did the rollback ({again}); "
                                  f"run `sudo fabricctl doctor`")
        raise ValidationError(f"{var}: {', '.join(s['name'] for s in services)} did not come back healthy on "
                              f"{target}; rolled back to {previous}")
    state = {}
    if os.path.exists(STATE):
        with open(STATE) as f:
            state = json.load(f)
    state[var] = {"previous": previous}
    os.makedirs(os.path.dirname(STATE), mode=0o700, exist_ok=True)
    fd = os.open(STATE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(state, f, indent=2)
    write_audit(actor, "IMAGE_UPDATE", f"{var} {previous} -> {target} ({', '.join(s['name'] for s in services)})",
                source)
    return [s["name"] for s in services]
