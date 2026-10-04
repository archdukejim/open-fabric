import os

from fabriclib.common.read_published_lock import read_published_lock
from fabriclib.images.constants import SERVICES
from fabriclib.images.effective_service import effective_service


def installed_services(ctx):
    """Purpose: the managed services this install has.
    Inputs:  ctx — SetupContext; a service counts when <deploy_base>/<folder>/docker-compose.yml exists.
    Returns: list of SERVICES entries (copies, from constants.py) as this host runs them (effective_service: a
             published image in use replaces the local build), in update order.
    Fails:   yaml.YAMLError or KeyError from read_published_lock on a broken lock.
    Feeds:   image_status, switch_image, rollback_image."""
    published = read_published_lock(ctx.target_dir).get("images") or {}
    return [effective_service(s, ctx.vars, published) for s in SERVICES
            if os.path.exists(ctx.path(s["folder"], "docker-compose.yml"))]
