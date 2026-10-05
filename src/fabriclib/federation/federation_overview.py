from fabriclib.common.errors import ValidationError
from fabriclib.federation.common.load_registry import load_registry
from fabriclib.federation.network_conflicts import network_conflicts
from fabriclib.federation.read_address_plan import read_address_plan
from fabriclib.samba.list_conflicts import list_conflicts
from fabriclib.samba.replication_status import replication_status

# each site's default write limits in the domain (manual 1.6.3.6): who, what it may write, beyond that
LIMITS = [
    ("fabric-agent-<site>, <site>-admins", "its own OU=<site> (people, groups, machines, devices, roles, networks, "
     "sudo rules, its GPOs), never its service accounts", "read only"),
    ("fabric-agent-<root>", "as a site's, plus OU=organisation, the domain's trust GPO and the password policy", ""),
    ("fabric-keycloak-<site>", "its site's people and groups (sign-in, password changes)", "read only"),
    ("fabric-radius-<site>", "nothing", "read only"),
]


def federation_overview(v):
    """Purpose: what the Federation tab shows (manual 1.8.8.9, 2.11.2.22 S8.5): this install's place, the sites that
             joined here with their DC types, this DC's replication with the others and AD's `CNF:` conflict
             objects, the default write limits, and the address plan with its overlaps.
    Inputs:  v — fabric vars (site_name, and what read_address_plan reads).
    Returns: {"site", "upstream" (record or None), "sites": [{name, domain, address, parent, dc, id_range, joined,
             via}], "replication": replication_status(), "conflicts": [DN], "limits": LIMITS rows, "plan": [network],
             "overlaps": [network_conflicts items with "site"], "plan_error": ""}.
    Fails:   yaml/OSError from load_registry for a malformed registry (the domain's own failures are shown, not raised).
    Feeds:   agent route GET /v1/federation (federation:read)."""
    registry = load_registry()
    sites = [{"name": name, **{k: rec.get(k, "") for k in ("domain", "address", "parent", "dc", "id_range", "joined",
                                                           "via")}}
             for name, rec in sorted(registry.get("sites", {}).items())]
    out = {"site": v.get("site_name", ""), "upstream": registry.get("upstream") or None, "sites": sites,
           "replication": replication_status(), "conflicts": list_conflicts(),
           "limits": [list(row) for row in LIMITS], "plan": [], "overlaps": [], "plan_error": ""}
    try:
        plan = read_address_plan(v)
    except ValidationError as e:
        out["plan_error"] = str(e)
        return out
    out["plan"] = plan
    for site in sorted({n["site"] for n in plan}):
        out["overlaps"] += [{**c, "site": site} for c in network_conflicts([n for n in plan if n["site"] == site],
                                                                           plan, site)]
    return out
