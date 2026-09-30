import os

from fabriclib.images.constants import SERVICES


def installed_services(ctx):
    """Purpose: the managed services this install has.
    Inputs:  ctx — SetupContext; a service counts when <deploy_base>/<folder>/docker-compose.yml exists.
    Returns: list of SERVICES entries (dicts from constants.py), in update order.
    Fails:   never — only file existence checks.
    Feeds:   image_status, switch_image."""
    return [s for s in SERVICES if os.path.exists(ctx.path(s["folder"], "docker-compose.yml"))]
