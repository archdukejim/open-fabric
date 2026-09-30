from fabriclib.common.read_images_lock import read_images_lock
from fabriclib.images.installed_services import installed_services
from fabriclib.images.running_image import running_image


def image_status(ctx):
    """Per installed service: the image it runs, the one this host is set to
    (vars), the validated one (images.lock.yaml of the installed fabric)
    and the state: current, update available, held (set by the admin),
    restart needed, not running. Read-only."""
    v = ctx.vars
    validated = {e["var"]: e["ref"] for e in read_images_lock(ctx.target_dir).values()}
    held = set(v.get("image_pins") or [])
    rows = []
    for s in installed_services(ctx):
        applied, running, want = v.get(s["var"]), running_image(s), validated.get(s["var"])
        if running is None:
            state = "not running"
        elif running != applied:
            state = "restart needed"
        elif want and applied != want:
            state = "held (set by the admin)" if s["var"] in held else "update available"
        else:
            state = "current"
        rows.append({"service": s["name"], "var": s["var"], "running": running, "applied": applied,
                     "validated": want, "state": state})
    return rows
