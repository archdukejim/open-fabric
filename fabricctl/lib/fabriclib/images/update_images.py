from fabriclib.common.errors import ValidationError
from fabriclib.images.image_status import image_status
from fabriclib.images.switch_image import switch_image


def update_images(ctx, names=None, force=False, actor="root", source="cli"):
    """Purpose: move services to their validated images (images.lock.yaml of the installed fabric).
             Services sharing an image var (image_debian: bind9, dirsrv, kea, freeradius, fabric-web) move together.
    Inputs:  ctx — SetupContext; names — list of service names, None = every service with an update;
             force — bool, also move images the admin set (state "held"); actor, source — for the audit log.
    Returns: list of (var, target ref, [service names moved]) in dependency order.
    Fails:   ValidationError for names not installed here; stops at the first switch_image failure
             (ValidationError; that service was rolled back, earlier vars stay updated).
    Feeds:   run_images_command (update)."""
    rows = image_status(ctx)
    known = {r["service"] for r in rows}
    unknown = set(names or ()) - known
    if unknown:
        raise ValidationError(f"not installed here: {', '.join(sorted(unknown))} (have: {', '.join(sorted(known))})")
    todo = []
    for r in rows:
        if names and r["service"] not in names:
            continue
        if r["state"] == "update available" or (force and r["state"].startswith("held")):
            if r["var"] not in [t[0] for t in todo]:
                todo.append((r["var"], r["validated"]))
    done = []
    for var, target in todo:                  # rows are in dependency order
        done.append((var, target, switch_image(ctx, var, target, actor, source)))
    return done
