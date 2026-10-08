from fabriclib.common.errors import ValidationError
from fabriclib.dhcp.normalize_options import NAME_RE

TYPES = {"binary", "boolean", "empty", "fqdn", "int8", "int16", "int32", "ipv4-address", "ipv6-address",
         "ipv6-prefix", "psid", "record", "string", "tuple", "uint8", "uint16", "uint32"}


def normalize_option_defs(defs):
    """Purpose: check dhcp.option_defs: options Kea has no name for (vendor or site-specific, e.g. a ZTP URL on
             code 239), so options can then name them (manual 1.10.2.3).
    Inputs:  defs — list of {name, code, type, space (default dhcp4), array, record_types}, or None.
    Returns: the definitions normalized (space only when not dhcp4; array only when true; record_types only for
             type record).
    Fails:   ValidationError: not a list; a bad name or space; code outside 1-254; an unknown type; a name or
             (space, code) defined twice; record without record_types. Kea refuses a definition that clashes
             with a standard option (deploy_kea's check).
    Feeds:   normalize_dhcp."""
    if defs is None:
        return []
    if not isinstance(defs, list):
        raise ValidationError("dhcp.option_defs must be a list")
    out, names, codes = [], set(), set()
    for d in defs:
        if not isinstance(d, dict):
            raise ValidationError(f"option definition {d!r}: name, code and type")
        name, space = str(d.get("name", "")).strip().lower(), str(d.get("space", "dhcp4")).strip().lower()
        code, kind = d.get("code"), str(d.get("type", "")).strip().lower()
        if not NAME_RE.match(name) or not NAME_RE.match(space):
            raise ValidationError(f"option definition {d.get('name')!r}: name and space are letters, digits, dashes")
        if isinstance(code, bool) or not isinstance(code, int) or not 1 <= code <= 254:
            raise ValidationError(f"option definition {name}: code is a number from 1 to 254")
        if kind not in TYPES:
            raise ValidationError(f"option definition {name}: type is one of {', '.join(sorted(TYPES))}")
        if (name, space) in names or (code, space) in codes:
            raise ValidationError(f"option definition {name} (code {code}) is defined twice in {space}")
        names.add((name, space))
        codes.add((code, space))
        entry = {"name": name, "code": code, "type": kind}
        if space != "dhcp4":
            entry["space"] = space
        if d.get("array") is True:
            entry["array"] = True
        if kind == "record":
            rt = str(d.get("record_types", "")).strip()
            if not rt:
                raise ValidationError(f"option definition {name}: type record needs record_types, e.g. uint8, string")
            entry["record_types"] = rt
        out.append(entry)
    return out
