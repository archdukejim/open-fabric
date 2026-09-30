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
    """Render and deploy with `var` = ref (local images rebuild on the new
    base), then recreate each service (compose down/up through its systemd
    unit) and wait until it is healthy."""
    ctx.vars[var] = ref
    deploy_config.run(ctx)
    for s in services:
        start_unit(s["unit"], s["container"], restart=True)


def switch_image(ctx, var, target, actor="root", source="cli"):
    """Move every service using image var `var` to `target` (a ref pinned by
    digest), one service at a time in dependency order, health-gated. If a
    service does not come back healthy, the previous ref is restored the
    same way and ValidationError is raised. The previous ref is remembered
    for `images rollback`. Returns the services moved."""
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
