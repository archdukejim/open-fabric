"""What an ADMX policy writes to the registry, as Windows' editor writes it (manual 1.6.5.9, S5.4): the values for
"enabled" with its elements, for "disabled", and which values belong to a policy (to clear it)."""
REG_SZ, REG_EXPAND_SZ, REG_DWORD = 1, 2, 4
TRUE_WORDS, FALSE_WORDS = {"1", "true", "on", "yes"}, {"0", "false", "off", "no"}


def _write(key, name, pair):
    """Purpose: one registry value from a template's (kind, value) pair: decimal → REG_DWORD, string → REG_SZ,
             delete → **del.
    Inputs:  key, name — str; pair — admx_store's (kind, value).
    Returns: [key, name, type, data].
    Fails:   ValueError for a decimal that is not a number.
    Feeds:   policy_entries, _element."""
    kind, value = pair
    if kind == "delete":
        return [key, "**del." + name, REG_SZ, " "]
    return [key, name, REG_DWORD, int(value)] if kind == "decimal" else [key, name, REG_SZ, str(value)]


def _element(el, given):
    """Purpose: the values one element writes for the text the admin gave.
    Inputs:  el — an element of read_policies; given — str.
    Returns: list of [key, name, type, data].
    Fails:   ValueError for a value of the wrong kind or an element kind not supported.
    Feeds:   policy_entries."""
    kind = el["type"]
    if kind == "decimal":
        if not given.lstrip("-").isdigit():
            raise ValueError(f"{el['id']}: a number")
        return [[el["key"], el["valueName"], REG_DWORD, int(given)]]
    if kind == "text":
        return [[el["key"], el["valueName"], REG_EXPAND_SZ if el["expandable"] else REG_SZ, given]]
    if kind == "boolean":
        word = given.lower()
        if word not in TRUE_WORDS | FALSE_WORDS:
            raise ValueError(f"{el['id']}: on or off")
        pair = (el["true"] or ("decimal", 1)) if word in TRUE_WORDS else (el["false"] or ("decimal", 0))
        return [_write(el["key"], el["valueName"], pair)]
    if kind == "enum":
        for i, (display, pair) in enumerate(el["items"]):
            if given == display or given == str(i):
                return [_write(el["key"], el["valueName"], pair)]
        raise ValueError(f"{el['id']}: one of " + ", ".join(f"{i} ({d})" for i, (d, _) in enumerate(el["items"])))
    if kind == "list":
        items = [x for x in given.split(";") if x]
        prefix = el.get("valuePrefix") or ""
        return [[el["key"], "**delvals.", REG_SZ, " "]] + [[el["key"], f"{prefix}{n}", REG_SZ, item]
                                                         for n, item in enumerate(items, 1)]
    raise ValueError(f"{el['id']}: {kind} elements are not supported yet")


def policy_entries(policy, values, enabled=True):
    """Purpose: the registry values a policy sets, as Windows' editor writes them into Registry.pol.
    Inputs:  policy — an admx_store.read_policies item; values — {element id: text} (decimal: a number; text: as
             given; boolean: on/off; enum: an item's name or number; list: items separated by ";"); enabled — False
             for "Disabled" (elements are deleted, the policy's own value set to its disabled value).
    Returns: list of [key, value name, type (1 REG_SZ, 2 REG_EXPAND_SZ, 4 REG_DWORD), data].
    Fails:   ValueError naming an element that is unknown, required and missing, or given a value of the wrong kind.
    Feeds:   gpo_tool (op "set")."""
    known = {el["id"]: el for el in policy["elements"]}
    for given in values:
        if given not in known:
            raise ValueError(f"{policy['name']} has no element {given} (it has: {', '.join(known) or 'none'})")
    out = []
    if policy["valueName"]:
        pair = (policy["enabled"] or ("decimal", 1)) if enabled else (policy["disabled"] or ("decimal", 0))
        out.append(_write(policy["key"], policy["valueName"], pair))
    for el in policy["elements"]:
        if not enabled:
            out.append([el["key"], "**delvals." if el["type"] == "list" else "**del." + (el["valueName"] or ""),
                        REG_SZ, " "])
        elif el["id"] in values:
            out += _element(el, values[el["id"]])
        elif el["required"]:
            raise ValueError(f"{policy['name']}: {el['id']} is required")
    return out


def policy_targets(policy):
    """Purpose: the registry values that belong to a policy, so setting or clearing it replaces only its own.
    Inputs:  policy — an admx_store.read_policies item.
    Returns: (set of (key lower, value name lower) for single values, set of key lower for lists: all their values).
    Fails:   never.
    Feeds:   gpo_tool (ops "set", "clear")."""
    single, whole = set(), set()
    if policy["valueName"]:
        single.add((policy["key"].lower(), policy["valueName"].lower()))
    for el in policy["elements"]:
        if el["type"] == "list":
            whole.add(el["key"].lower())
        elif el["valueName"]:
            single.add((el["key"].lower(), el["valueName"].lower()))
            single.add((el["key"].lower(), "**del." + el["valueName"].lower()))
    if policy["valueName"]:
        single.add((policy["key"].lower(), "**del." + policy["valueName"].lower()))
    return single, whole
