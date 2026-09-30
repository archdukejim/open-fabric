from fabriclib.common.errors import ValidationError
from fabriclib.ldap.constants import PERMISSIONS


def check_role_fields(fields):
    """Validate a device role's settings. Returns {description,
    permissions, vlan (None or 1..4094), priority (0..1000, default 100)}."""
    perms = sorted(set(fields.get("permissions") or []))
    unknown = [p for p in perms if p not in PERMISSIONS]
    if unknown:
        raise ValidationError(f"unknown permission: {', '.join(unknown)}")
    vlan = str(fields.get("vlan") or "").strip()
    if vlan:
        if not vlan.isdigit() or not 1 <= int(vlan) <= 4094:
            raise ValidationError("VLAN must be 1 to 4094 (or empty)")
        vlan = int(vlan)
    priority = str(fields.get("priority") if fields.get("priority") not in (None, "") else 100).strip()
    if not priority.isdigit() or int(priority) > 1000:
        raise ValidationError("priority must be 0 to 1000")
    description = str(fields.get("description") or "").strip()
    if len(description) > 200 or "\n" in description:
        raise ValidationError("description: one line, at most 200 characters")
    return {"description": description, "permissions": perms, "vlan": vlan or None, "priority": int(priority)}
