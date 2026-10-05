from agent.read_fields import read_fields
from agent.read_text import read_text
from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.directory.add_device import add_device
from fabriclib.directory.add_role import add_role
from fabriclib.directory.link_device_cert import link_device_cert
from fabriclib.directory.remove_device import remove_device
from fabriclib.directory.remove_role import remove_role
from fabriclib.directory.update_device import update_device
from fabriclib.directory.update_role import update_role


def post_directory(route, actor, data):
    """Purpose: devices and device roles in the domain, POST /v1/devices/... and /v1/roles/... (fabriclib.directory,
             as the site's agent account).
    Inputs:  route — ["devices"|"roles"] plus [], [<name>], [<name>,"delete"] or (devices only) [<name>,"certs"];
             actor — str; data — body: name, fields (read_fields), sha256, link.
    Returns: {"name": ...} for an add; the result of update_*/remove_* or link_device_cert otherwise ({} when None).
    Fails:   ValidationError("unknown operation") for another route, or from the readers and fabriclib (-> 400).
    Feeds:   agent/post_route.py (POST devices/..., roles/...)."""
    v = load_vars()
    kind, rest = route[0], route[1:]
    add, update, remove = ((add_device, update_device, remove_device) if kind == "devices"
                           else (add_role, update_role, remove_role))
    if not rest:
        return {"name": add(v, actor, read_text(data, "name"), read_fields(data), source="web")}
    if len(rest) == 1:
        return update(v, actor, rest[0], read_fields(data), source="web") or {}
    if rest[1:] == ["delete"]:
        return remove(v, actor, rest[0], source="web") or {}
    if kind == "devices" and rest[1:] == ["certs"]:
        return link_device_cert(v, actor, rest[0], read_text(data, "sha256"), bool(data.get("link", True)),
                                source="web") or {}
    raise ValidationError("unknown operation")
