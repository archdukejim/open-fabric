import json
import os

from fabriclib.common.errors import ValidationError
from fabriclib.images.constants import SERVICES, STATE
from fabriclib.images.switch_image import switch_image


def rollback_image(ctx, name, actor="root", source="cli"):
    """Move a service (and any sharing its base) back to the image it ran
    before its last update. Returns the services moved."""
    service = next((s for s in SERVICES if s["name"] == name), None)
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
