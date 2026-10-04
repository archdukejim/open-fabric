import re

from fabriclib.common.errors import ValidationError

NAME_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")     # Kea's option names and option spaces
MAX_DATA = 1024


def normalize_options(options, where):
    """Purpose: check a list of DHCP options as fabric stores them (manual 2.2.2.3): Kea's own
             option-data at global, class, subnet or reservation level.
    Inputs:  options — list of {name | code, data, space (default dhcp4), csv_format, always_send}, or None;
             where — what the list belongs to, for messages ("dhcp.options", "subnet iot", ...).
    Returns: the options normalized: name (lower-case) or code (int), data (str, "" allowed for options without
             data), space only when not dhcp4, csv_format / always_send only when given (bool). [] for None.
    Fails:   ValidationError: not a list; an entry that is not a mapping; neither or both of name and code; a bad
             name or space; a code outside 1-254; data not text or longer than 1024 characters (or with a line
             break); csv_format / always_send not true/false; the same option twice in one list. Kea's own check
             (deploy_kea, `kea-dhcp4 -t`) decides whether a name exists and its data fits.
    Feeds:   normalize_dhcp (every level), dhcp/set_option."""
    if options is None:
        return []
    if not isinstance(options, list):
        raise ValidationError(f"{where}: options must be a list")
    out, seen = [], set()
    for o in options:
        if not isinstance(o, dict):
            raise ValidationError(f"{where}: an option is {{name or code, data}}, not {o!r}")
        if ("name" in o) == ("code" in o):
            raise ValidationError(f"{where}: an option has a name or a code (not both): {o}")
        entry = {}
        if "name" in o:
            name = str(o["name"]).strip().lower()
            if not NAME_RE.match(name):
                raise ValidationError(f"{where}: option name {o['name']!r}: letters, digits and dashes, e.g. "
                                      "tftp-server-name")
            entry["name"] = name
        else:
            code = o["code"]
            if isinstance(code, bool) or not isinstance(code, int) or not 1 <= code <= 254:
                raise ValidationError(f"{where}: option code {code!r}: a number from 1 to 254")
            entry["code"] = code
        data = o.get("data", "")
        if isinstance(data, bool) or not isinstance(data, (str, int, float)):
            raise ValidationError(f"{where}: option {entry.get('name', entry.get('code'))}: data is text")
        data = str(data)
        if len(data) > MAX_DATA or "\n" in data or "\r" in data:
            raise ValidationError(f"{where}: option {entry.get('name', entry.get('code'))}: data is one line of "
                                  f"at most {MAX_DATA} characters")
        entry["data"] = data
        space = str(o.get("space", "dhcp4")).strip().lower()
        if not NAME_RE.match(space):
            raise ValidationError(f"{where}: option space {o.get('space')!r}: letters, digits and dashes")
        if space != "dhcp4":
            entry["space"] = space
        for flag in ("csv_format", "always_send"):
            if flag in o:
                if not isinstance(o[flag], bool):
                    raise ValidationError(f"{where}: option {flag} is true or false")
                entry[flag] = o[flag]
        key = (entry.get("name", entry.get("code")), space)
        if key in seen:
            raise ValidationError(f"{where}: option {key[0]} is set twice")
        seen.add(key)
        out.append(entry)
    return out
