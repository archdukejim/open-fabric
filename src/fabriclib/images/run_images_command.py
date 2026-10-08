import sys

from fabriclib.common.errors import ValidationError
from fabriclib.images.image_status import image_status
from fabriclib.images.prune_images import prune_images
from fabriclib.images.rollback_image import rollback_image
from fabriclib.images.update_images import update_images

USAGE = """usage: fabricctl images status                  each service: running, validated, update available?
       fabricctl images update <service…>|--all [--force]
                                               move to the validated images (compose down/up per service,
                                               health-gated, rolled back on failure); --force: also images
                                               the admin set in vars.yaml
       fabricctl images rollback <service>     back to the image before the last update
       fabricctl images prune                  remove old images of fabric's repositories (not in use,
                                               not the rollback image)"""


def _short(ref):
    """Purpose: a short display form of an image ref.
    Inputs:  ref — str "repo:tag@sha256:…" or None/"".
    Returns: str "repo:tag@<12 hex chars of the digest>", the ref unchanged without a digest, or "—" when empty.
    Fails:   never.
    Feeds:   run_images_command."""
    if not ref:
        return "—"
    name, _, digest = ref.partition("@")
    return f"{name}@{digest[7:19]}" if digest else name


def _prune(ctx):
    """Purpose: after an update, remove old images unless the admin turned it off.
    Inputs:  ctx — SetupContext; reads vars image_prune (default true).
    Returns: None; prints how many images were cleaned up.
    Fails:   whatever prune_images raises.
    Feeds:   run_images_command (update)."""
    if ctx.vars.get("image_prune", True):
        removed = prune_images(ctx)
        print(f"cleaned up {len(removed)} old image(s)" if removed else "no old images to clean up")


def run_images_command(ctx, argv):
    """Purpose: route `fabricctl images status|update|rollback|prune` (design 2.1.14.3) and print the results.
             Nothing here runs on its own; applying is these commands.
    Inputs:  ctx — SetupContext with state loaded; argv — list of str after "images" (empty = status).
    Returns: exit status int: 0 done, 1 ValidationError (printed to stderr), 2 usage error (usage printed).
    Fails:   ValidationError is caught and becomes exit 1; other errors (Docker, YAML, SetupError from deploy)
             propagate to the caller.
    Feeds:   cli.py (`fabricctl images`)."""
    cmd, args = (argv[0], argv[1:]) if argv else ("status", [])
    try:
        if cmd == "status" and not args:
            rows = image_status(ctx)
            for r in rows:
                line = f"{r['service']:<9} {r['state']:<24} runs {_short(r['running'])}"
                if r["state"] in ("update available", "held (set by the admin)"):
                    line += f"  →  {_short(r['validated'])}"
                print(line)
            n = sum(r["state"] == "update available" for r in rows)
            print(f"\n{n} update(s) available: sudo fabricctl images update --all" if n else "\nall images current")
            return 0
        if cmd == "update" and args:
            names = None if "--all" in args else [a for a in args if not a.startswith("--")]
            done = update_images(ctx, names, force="--force" in args)
            for var, target, services in done:
                print(f"updated {', '.join(services)} → {_short(target)}")
            if not done:
                print("nothing to update")
            else:
                _prune(ctx)
            return 0
        if cmd == "rollback" and len(args) == 1:
            moved = rollback_image(ctx, args[0])
            print(f"rolled back {', '.join(moved)}" if moved else "already on the previous image")
            return 0
        if cmd == "prune" and not args:
            removed = prune_images(ctx)
            for r in removed:
                print(f"removed {r}")
            print(f"{len(removed)} old image(s) removed")
            return 0
    except ValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(USAGE, file=sys.stderr)
    return 2
