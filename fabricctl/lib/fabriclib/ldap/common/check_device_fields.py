from fabriclib.common.errors import ValidationError
from fabriclib.ldap.common.normalize_mac import normalize_mac
from fabriclib.ldap.constants import DEVICE_TYPES, USER_RE


def check_device_fields(fields, directory, name):
    """Validate the editable fields of device `name` against the current
    directory ({devices, roles}). Returns {type, macs, owner, description,
    enabled, roles} normalised. A MAC may belong to one device only (MAC
    authentication must be unambiguous); roles must exist."""
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
