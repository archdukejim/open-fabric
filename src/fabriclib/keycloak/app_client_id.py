import re

from fabriclib.common.errors import ValidationError

PREFIX = "app-"                     # apps' clients are never fabric's own (fabric-webui, fabric-openbao, …)
NAME_RE = re.compile(r"^[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])?$")


def app_client_id(name):
    """Purpose: the Keycloak client id of an app registered for single sign-on (manual 4.6.2).
    Inputs:  name — the app's short name, e.g. "proxmox": 1-40 lower-case letters, digits or dashes.
    Returns: str "app-<name>".
    Fails:   ValidationError for a name that is not one.
    Feeds:   add_app_client, remove_app_client."""
    name = str(name).strip().lower()
    if not NAME_RE.match(name):
        raise ValidationError(f"{name!r}: an app's name is 1-40 lower-case letters, digits or dashes")
    return PREFIX + name
