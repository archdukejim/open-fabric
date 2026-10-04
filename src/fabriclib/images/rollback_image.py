import json
import os

from fabriclib.common.errors import ValidationError
from fabriclib.images.constants import SERVICES, STATE
from fabriclib.images.installed_services import installed_services
from fabriclib.images.switch_image import switch_image


def rollback_image(ctx, name, actor="root", source="cli"):
    """Purpose: move a service (and every service sharing its image var) back to the image it ran before
             its last `fabricctl images update`.
    Inputs:  ctx — SetupContext; name — str, a service name from SERVICES; actor, source — for the audit log.
             Reads the rollback STATE file.
    Returns: list of service names moved; [] if already on that image.
    Fails:   ValidationError for an unknown service or when no previous image is recorded; everything
             switch_image raises (ValidationError on a failed pull or failed health check);
             json.JSONDecodeError if STATE is corrupt.
    Feeds:   run_images_command (rollback)."""
    # as this host runs it: a published image in use has its own var (manual 2.6.3.5)
    service = (next((s for s in installed_services(ctx) if s["name"] == name), None)
               or next((s for s in SERVICES if s["name"] == name), None))
    if service is None:
        raise ValidationError(f"unknown service {name!r}")
    state = {}
    if os.path.exists(STATE):
        with open(STATE) as f:
            state = json.load(f)
    previous = (state.get(service["var"]) or {}).get("previous")
    if not previous:
        raise ValidationError(f"{name}: no previous image recorded (never updated with `fabricctl images update`)")
    return switch_image(ctx, service["var"], previous, actor, source)
