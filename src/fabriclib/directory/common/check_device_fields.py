from fabriclib.common.errors import ValidationError
from fabriclib.ldap.common.normalize_mac import normalize_mac
from fabriclib.ldap.constants import DEVICE_TYPES, USER_RE


def check_device_fields(fields, directory, name):
    """Purpose: Validate and normalise the editable fields of a device against the current directory.
    Inputs:  fields — dict: type (DEVICE_TYPES, default "other"), macs (list, any common spelling),
             owner (username, optional), description, enabled (default True), roles (list of role names);
             directory — read_directory result; name — the device being saved (its own MACs do not clash).
    Returns: {"type", "macs" (normalised, de-duplicated), "owner", "description", "enabled" (bool),
             "roles" (sorted, unique)}.
    Fails:   ValidationError "type must be one of ..."; normalize_mac's "not a MAC address: ..." / "... is a
             multicast address, not a device"; "MAC ... already belongs to device ..."; "invalid owner
             username: ..."; "description: one line, at most 200 characters"; "no such role: ...".
    Feeds:   add_device, update_device; the web UI's dev preview (src/webui/devpreview).
    Notes:   a MAC may belong to one device only, so MAC authentication stays unambiguous. The owner's
             existence is checked later, in the directory.
    """
    dtype = str(fields.get("type") or "other")
    if dtype not in DEVICE_TYPES:
        raise ValidationError(f"type must be one of {', '.join(DEVICE_TYPES)}")
    macs = list(dict.fromkeys(normalize_mac(m) for m in fields.get("macs") or [] if str(m).strip()))
    for d in directory["devices"]:
        taken = set(macs) & set(d["macs"])
        if d["name"] != name and taken:
            raise ValidationError(f"MAC {', '.join(sorted(taken))} already belongs to device {d['name']}")
    owner = str(fields.get("owner") or "").strip()
    if owner and not USER_RE.match(owner):
        raise ValidationError(f"invalid owner username: {owner!r}")
    description = str(fields.get("description") or "").strip()
    if len(description) > 200 or "\n" in description:
        raise ValidationError("description: one line, at most 200 characters")
    known = {r["name"] for r in directory["roles"]}
    roles = sorted(set(fields.get("roles") or []))
    unknown = [r for r in roles if r not in known]
    if unknown:
        raise ValidationError(f"no such role: {', '.join(unknown)}")
    return {"type": dtype, "macs": macs, "owner": owner, "description": description,
            "enabled": bool(fields.get("enabled", True)), "roles": roles}
