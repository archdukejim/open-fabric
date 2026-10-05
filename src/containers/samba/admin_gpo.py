"""The site's `fabric: <site> admin settings` GPO (manual 2.11.2.20, S5.4): the policies an admin sets with
`fabricctl gpo` (the web UI's editor in S7), kept apart from fabric's own GPOs, which convergence rewrites."""
import os

import ldb
from samba.dcerpc import preg
from samba.ndr import ndr_pack, ndr_unpack

from ensure_gpo import ensure_gpo
import paths

REGISTRY_MACHINE = "[{35378EAC-683F-11D2-A89A-00C04FBBCFA2}{0F6B957D-509E-11D1-A7CC-0000F87571E3}]"
REGISTRY_USER = "[{35378EAC-683F-11D2-A89A-00C04FBBCFA2}{0F6B957E-509E-11D1-A7CC-0000F87571E3}]"


def _name(site):
    """Purpose: the site's admin GPO's display name.
    Inputs:  site — str.
    Returns: str "fabric: <site> admin settings".
    Fails:   never.
    Feeds:   admin_settings, save_admin_settings."""
    return f"fabric: {site} admin settings"


def admin_settings(samdb, lp, site):
    """Purpose: what the site's admin GPO sets today.
    Inputs:  samdb — SamDB (as the system); lp — LoadParm; site — str.
    Returns: {"machine": [[key, value name, type, data]], "user": [...]}; both empty before anything was set.
    Fails:   ldb.LdbError; OSError reading SYSVOL.
    Feeds:   gpo_tool (ops "show", "set", "clear")."""
    out = {"machine": [], "user": []}
    found = samdb.search(base=f"CN=Policies,CN=System,{samdb.domain_dn()}", scope=ldb.SCOPE_ONELEVEL,
                         expression=f"(displayName={ldb.binary_encode(_name(site))})", attrs=["cn"])
    if not found:
        return out
    folder = os.path.join(lp.get("path", "sysvol"), lp.get("realm").lower(), "Policies", str(found[0]["cn"]))
    for scope, sub in (("machine", "Machine"), ("user", "User")):
        path = os.path.join(folder, sub, "Registry.pol")
        if os.path.exists(path):
            pol = ndr_unpack(preg.file, open(path, "rb").read())
            out[scope] = [[e.keyname, e.valuename, e.type, e.data] for e in pol.entries]
    return out


def _pack(entries):
    """Purpose: a Registry.pol file of these entries (Samba's PReg encoding).
    Inputs:  entries — list of [key, name, type, data].
    Returns: bytes.
    Fails:   TypeError for data of the wrong type for its value type.
    Feeds:   save_admin_settings."""
    f = preg.file()
    f.header.signature, f.header.version = "PReg", 1
    items = []
    for key, name, kind, data in entries:
        e = preg.entry()
        e.keyname, e.valuename, e.type, e.data = key, name, kind, data
        items.append(e)
    f.num_entries = len(items)          # before the entries: NDR sizes the array by it
    f.entries = items
    return ndr_pack(f)


def save_admin_settings(samdb, lp, site, settings):
    """Purpose: write the site's admin GPO (created and linked to the site's OU when missing), its version bumped.
    Inputs:  samdb — SamDB (as the system); lp — LoadParm; site — str; settings — admin_settings' shape.
    Returns: list of str, what changed.
    Fails:   ldb.LdbError; OSError; CalledProcessError (ensure_gpo).
    Feeds:   gpo_tool (ops "set", "clear")."""
    return ensure_gpo(samdb, lp, _name(site), paths.site_dn(samdb, site),
                      REGISTRY_MACHINE if settings["machine"] else "",
                      {"Machine/Registry.pol": _pack(settings["machine"]),
                       "User/Registry.pol": _pack(settings["user"])},
                      user_extensions=REGISTRY_USER if settings["user"] else "")
