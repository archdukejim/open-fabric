from fabriclib.common.errors import ValidationError


def read_fields(data):
    """Purpose: validate the "fields" form of a device or role request.
    Inputs:  data — the request body; data["fields"] must be an object of at most 20 entries whose values are text,
             booleans, or lists of at most 100 strings. Missing or empty means {}.
    Returns: dict, the fields unchanged.
    Fails:   ValidationError("fields must be an object") or ("field <k> has an unsupported value") (-> 400).
    Feeds:   post_directory (add_device, add_role, update_device, update_role)."""
    value = data.get("fields") or {}
    if not isinstance(value, dict) or len(value) > 20:
        raise ValidationError("fields must be an object")
    for k, x in value.items():
        ok = isinstance(x, (str, bool)) or (isinstance(x, list) and len(x) <= 100 and all(isinstance(i, str) for i in x))
        if not ok:
            raise ValidationError(f"field {k} has an unsupported value")
    return value
