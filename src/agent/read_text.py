from fabriclib.common.errors import ValidationError


def read_text(data, field):
    """Purpose: read one text field from a request body.
    Inputs:  data — the request body; field — str, the key.
    Returns: str, the value; "" when absent.
    Fails:   ValidationError("<field> must be text") when present but not a string (-> 400).
    Feeds:   every post_* route module."""
    value = data.get(field, "")
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be text")
    return value
