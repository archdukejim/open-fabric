"""The domain's central store of ADMX templates (manual 2.11.2.9, S5.4): SYSVOL's Policies/PolicyDefinitions, read by
Windows' own editor too. Templates are parsed the way Windows' editor reads them (Microsoft's and Samba's forms)."""
import os
import subprocess
import xml.etree.ElementTree as ET

LANGUAGE = "en-US"


def store_dir(lp):
    """Purpose: the central store's folder.
    Inputs:  lp — LoadParm of the DC.
    Returns: str, <sysvol>/<realm>/Policies/PolicyDefinitions.
    Fails:   never.
    Feeds:   save_templates, read_policies."""
    return os.path.join(lp.get("path", "sysvol"), lp.get("realm").lower(), "Policies", "PolicyDefinitions")


def save_templates(lp, files):
    """Purpose: put ADMX templates and their ADML language files into the central store (`fabricctl gpo load`).
    Inputs:  lp — LoadParm; files — {"<name>.admx" or "<lang>/<name>.adml": bytes}.
    Returns: list of str, the files written.
    Fails:   ValueError for a name that is not a template or language file, or an ADMX that does not parse;
             OSError writing; CalledProcessError from `samba-tool ntacl sysvolreset`.
    Feeds:   gpo_tool (op "load")."""
    done = []
    for name, data in sorted(files.items()):
        parts = name.split("/")
        if not (len(parts) == 1 and name.lower().endswith(".admx")
                or len(parts) == 2 and parts[1].lower().endswith(".adml") and "." not in parts[0]
                and parts[0] not in ("", "..")) or any(p.startswith(".") for p in parts):
            raise ValueError(f"not an ADMX template or ADML language file: {name}")
        ET.fromstring(data)                     # refuse what does not parse before anything is written
        path = os.path.join(store_dir(lp), *parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "wb") as f:
            f.write(data)
        done.append(name)
    subprocess.run(["samba-tool", "ntacl", "sysvolreset", "-s", lp.configfile], check=True, capture_output=True)
    return done


def _local(tag):
    """Purpose: an element's name without its namespace (Microsoft's templates declare one, Samba's do not).
    Inputs:  tag — str.
    Returns: str.
    Fails:   never.
    Feeds:   read_policies, _child, _value."""
    return tag.split("}")[-1]


def _child(e, name):
    """Purpose: an element's first child of that name.
    Inputs:  e — Element; name — str.
    Returns: Element or None.
    Fails:   never.
    Feeds:   read_policies, _value."""
    return next((c for c in e if _local(c.tag) == name), None)


def _value(e):
    """Purpose: a <value>-like element's registry value.
    Inputs:  e — Element or None.
    Returns: ("decimal", int), ("string", str), ("delete", None), or None.
    Fails:   ValueError for a decimal that is not a number.
    Feeds:   read_policies."""
    if e is None:
        return None
    for c in e:
        if _local(c.tag) == "decimal":
            return ("decimal", int(c.get("value")))
        if _local(c.tag) == "string":
            return ("string", c.text or "")
        if _local(c.tag) == "delete":
            return ("delete", None)
    return None


def read_policies(lp):
    """Purpose: every policy the central store's templates define, with their names and elements.
    Inputs:  lp — LoadParm.
    Returns: list of {"template", "name", "display", "class" (Machine/User/Both), "key", "valueName",
             "enabled"/"disabled" (a _value pair or None), "elements": [{"id", "type" (decimal, text, boolean, enum,
             list), "key", "valueName", "required", "expandable", "true"/"false" (booleans), "items" ([display,
             value] for enums), "valuePrefix" (lists)}]}, sorted by template and name.
    Fails:   xml.etree.ElementTree.ParseError for a template that does not parse.
    Feeds:   gpo_tool (ops "policies", "set", "clear")."""
    out = []
    folder = store_dir(lp)
    for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
        if not name.lower().endswith(".admx"):
            continue
        adml = os.path.join(folder, LANGUAGE, name[:-5] + ".adml")
        strings = {}
        if os.path.exists(adml):
            strings = {s.get("id"): (s.text or "") for s in ET.parse(adml).getroot().iter()
                       if _local(s.tag) == "string"}

        def text(ref):
            return strings.get(ref[len("$(string."):-1], ref) if ref and ref.startswith("$(string.") else (ref or "")

        for pol in (p for p in ET.parse(os.path.join(folder, name)).getroot().iter() if _local(p.tag) == "policy"):
            key = pol.get("key")
            elements = []
            for el in list(_child(pol, "elements") if _child(pol, "elements") is not None else []):
                kind = _local(el.tag)
                elements.append({
                    "id": el.get("id"), "type": kind, "key": el.get("key") or key, "valueName": el.get("valueName"),
                    "required": el.get("required") == "true", "expandable": el.get("expandable") == "true",
                    "true": _value(_child(el, "trueValue")), "false": _value(_child(el, "falseValue")),
                    "items": [[text(i.get("displayName")), _value(_child(i, "value"))]
                              for i in el if _local(i.tag) == "item"],
                    "valuePrefix": el.get("valuePrefix")})
            out.append({"template": name[:-5], "name": pol.get("name"), "display": text(pol.get("displayName")),
                        "class": pol.get("class") or "Machine", "key": key, "valueName": pol.get("valueName"),
                        "enabled": _value(_child(pol, "enabledValue")),
                        "disabled": _value(_child(pol, "disabledValue")), "elements": elements})
    return out
