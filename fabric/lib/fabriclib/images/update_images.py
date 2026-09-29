from fabriclib.common.errors import ValidationError
from fabriclib.images.image_status import image_status
from fabriclib.images.switch_image import switch_image


def update_images(ctx, names=None, force=False, actor="root", source="cli"):
    """Move services to their validated images (images.lock.yaml of the
    installed fabric). `names`: services to update, None = every service
    with an update. Images the admin set explicitly are skipped unless
    `force`. Services sharing a base (bind9, dirsrv and fabric-web on Debian)
    move together. Stops at the first failure (that service is rolled back).
    Returns [(var, target, [services])]."""
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
