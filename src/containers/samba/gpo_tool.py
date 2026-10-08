"""fabric's ADMX editor inside the DC (manual 1.6.5.9, 1.6.5.20 S5.4), run as root on its own database and SYSVOL
(no credentials, no network) by fabriclib/samba/run_gpo_command:
    docker exec -i samba python3 /fabric/gpo_tool.py < request.json
The request on stdin: {"op": "load"|"templates"|"policies"|"show"|"set"|"clear", "site", …}. Prints one JSON object:
{"result": …} or {"error": message} (exit 0 either way)."""
import base64
import json
import os
import sys

from admin_gpo import admin_settings, save_admin_settings
from admx_store import read_policies, save_templates, store_dir
from open_samdb import open_samdb
from policy_entries import policy_entries, policy_targets

CONF = "/data/etc/smb.conf"


def _policy(lp, name):
    """Purpose: the policy of that name (or display name) in the central store.
    Inputs:  lp — LoadParm; name — str.
    Returns: a read_policies item.
    Fails:   ValueError when none, or several, match.
    Feeds:   run."""
    found = [p for p in read_policies(lp) if name in (p["name"], p["display"])]
    if len(found) != 1:
        raise ValueError(f"no policy {name} in the central store" if not found else f"{name} names several policies")
    return found[0]


def _without(entries, policy):
    """Purpose: a GPO's entries less those that belong to the policy.
    Inputs:  entries — list of [key, name, type, data]; policy — a read_policies item.
    Returns: list.
    Fails:   never.
    Feeds:   run."""
    single, whole = policy_targets(policy)
    return [e for e in entries if (e[0].lower(), e[1].lower()) not in single and e[0].lower() not in whole]


def run(req):
    """Purpose: one editor operation.
    Inputs:  req — {"op", "site", and per op: "files" {name: base64} (load); "match" (policies); "policy", "values"
             {element id: text}, "enabled" bool (set); "policy" (clear); "control" bool (show, set, clear: the
             site's enforced controls GPO instead of its admin settings)}.
    Returns: load: the files written; templates: the store's templates; policies: the matching policies (name,
             display, class, template, elements); show: the admin GPO's values; set/clear: what changed.
    Fails:   ValueError for a request the editor refuses (its message is shown); ldb.LdbError, OSError.
    Feeds:   this script's main."""
    samdb, lp = open_samdb(CONF)
    op, site = req["op"], req.get("site", "")
    if op == "load":
        return save_templates(lp, {n: base64.b64decode(d) for n, d in req["files"].items()})
    if op == "templates":
        folder = store_dir(lp)
        names = os.listdir(folder) if os.path.isdir(folder) else []
        return sorted(n[:-5] for n in names if n.lower().endswith(".admx"))
    if op == "policies":
        match = (req.get("match") or "").lower()
        return [{k: p[k] for k in ("template", "name", "display", "class")}
                | {"elements": [f"{e['type']}:{e['id']}" for e in p["elements"]]}
                for p in read_policies(lp) if match in (p["name"] + " " + p["display"]).lower()]
    control = bool(req.get("control"))
    if op == "show":
        return admin_settings(samdb, lp, site, control)
    if op in ("set", "clear"):
        policy = _policy(lp, req["policy"])
        settings = admin_settings(samdb, lp, site, control)
        scope = "user" if policy["class"] == "User" else "machine"
        settings[scope] = _without(settings[scope], policy)
        if op == "set":
            settings[scope] += policy_entries(policy, req.get("values") or {}, bool(req.get("enabled", True)))
        return save_admin_settings(samdb, lp, site, settings, control)
    raise ValueError(f"unknown operation {op}")


if __name__ == "__main__":
    try:
        print(json.dumps({"result": run(json.load(sys.stdin))}))
    except ValueError as e:                  # the editor's own refusals: shown as they are
        print(json.dumps({"error": str(e)}))
    except Exception as e:                   # anything else: its kind, for the log
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}))
