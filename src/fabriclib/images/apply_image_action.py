from fabriclib.common.errors import ValidationError
from fabriclib.images.prune_images import prune_images
from fabriclib.images.rollback_image import rollback_image
from fabriclib.images.update_images import update_images
from fabriclib.setup.context import SetupContext


def apply_image_action(action, service, actor, deploy_base="/opt"):
    """Purpose: update one service to its validated image, or roll it back, from the web console (2.1.8.3, manual
             1.14.2): what `fabricctl images update <service>` and `rollback <service>` do, health-gated, audited with
             the person who asked.
    Inputs:  action — "update" or "rollback"; service — a service name from `images status`; actor — str (audit);
             deploy_base — the install root. Runs as root (fabric-agent).
    Returns: {"action", "service", "moved": [service names], "message": str}.
    Fails:   ValidationError "action: update or rollback", or from update_images / rollback_image (not installed here,
             no previous image); a failed switch is rolled back by switch_image and raised.
    Feeds:   agent job "images" (POST /v1/jobs/images)."""
    if action not in ("update", "rollback"):
        raise ValidationError("action: update or rollback")
    ctx = SetupContext(deploy_base=deploy_base).load_state()
    if action == "rollback":
        moved = rollback_image(ctx, service, actor=actor, source="web")
        message = f"rolled back {', '.join(moved)}" if moved else f"{service} is already on its previous image"
    else:
        done = update_images(ctx, [service], actor=actor, source="web")
        moved = [s for _, _, services in done for s in services]
        message = f"updated {', '.join(moved)}" if moved else f"{service}: nothing to update"
        if moved and ctx.vars.get("image_prune", True):
            prune_images(ctx)
    return {"action": action, "service": service, "moved": moved, "message": message}
