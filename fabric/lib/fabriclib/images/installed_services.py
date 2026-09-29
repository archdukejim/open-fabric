import os

from fabriclib.images.constants import SERVICES


def installed_services(ctx):
    """The managed services this install has (a compose file is deployed)."""
    return [s for s in SERVICES if os.path.exists(ctx.path(s["folder"], "docker-compose.yml"))]
