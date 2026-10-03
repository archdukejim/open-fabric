from agent.read_strings import read_strings
from agent.read_text import read_text
from agent.route_not_found import RouteNotFound
from fabriclib.common.errors import ValidationError
from fabriclib.common.load_vars import load_vars
from fabriclib.dhcp.add_client_class import add_client_class
from fabriclib.dhcp.add_reservation import add_reservation
from fabriclib.dhcp.add_subnet import add_subnet
from fabriclib.dhcp.list_leases import list_leases
from fabriclib.dhcp.remove_client_class import remove_client_class
from fabriclib.dhcp.remove_reservation import remove_reservation
from fabriclib.dhcp.remove_subnet import remove_subnet
from fabriclib.dhcp.set_option import set_option
from fabriclib.dhcp.unset_option import unset_option
from fabriclib.dhcp.update_subnet import KEEP, update_subnet
from fabriclib.system.apply_changes import apply_changes


def _vlan(data):
    """Purpose: the vlan field: a number 1-4094 as text or number, "" to clear, absent to leave it.
    Inputs:  data — the request body.
    Returns: KEEP (absent), None ("" or null) or int.
    Fails:   ValidationError for anything else (-> 400).
    Feeds:   post_dhcp."""
    if "vlan" not in data:
        return KEEP
    value = data["vlan"]
    if value in (None, ""):
        return None
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value)
    raise ValidationError("vlan must be a number from 1 to 4094")


def _where(data):
    """Purpose: where an option goes: subnet, class or mac from the body (none: every subnet).
    Inputs:  data — the request body.
    Returns: {"subnet", "client_class", "mac"} (each str or None).
    Fails:   ValidationError from read_text (-> 400).
    Feeds:   post_dhcp."""
    return {"subnet": read_text(data, "subnet") or None, "client_class": read_text(data, "class") or None,
            "mac": read_text(data, "mac") or None}


def post_dhcp(route, actor, data):
    """Purpose: DHCP changes from the Kea tab, each saved and applied at once (design dhcp-management.md §4):
             POST /v1/dhcp/reservations[/<mac>/delete], /v1/dhcp/subnets, /v1/dhcp/subnets/update,
             /v1/dhcp/subnets/delete, /v1/dhcp/options, /v1/dhcp/options/delete, /v1/dhcp/classes,
             /v1/dhcp/classes/<name>/delete.
    Inputs:  route — segments after /v1/; actor — the verified user; data — the body: mac, ip, hostname
             (reservations); network, name, vlan, router, pools, notes, allow_overlap (add); subnet (name or
             network), name, vlan, router, notes, allow_overlap, add_pools, remove_pools (update; a field left out
             stays, "" clears it); subnet, force
             (delete); option, data, subnet | class | mac, always_send (options); name, test, next_server,
             boot_file (classes).
    Returns: the saved item, with "applied" (bool) and the last 2000 characters of the apply's output.
    Fails:   ValidationError from the readers and fabriclib (-> 400); RouteNotFound for another route.
    Feeds:   agent/post_route.py."""
    sub = route[1:]
    if sub == ["reservations"]:
        result = {"reservation": add_reservation(actor, read_text(data, "mac"), read_text(data, "ip"),
                                                 read_text(data, "hostname"), source="web")}
    elif len(sub) == 3 and sub[0] == "reservations" and sub[2] == "delete":
        remove_reservation(actor, sub[1], source="web")
        result = {}
    elif sub == ["subnets"]:
        vlan = _vlan(data)
        result = {"subnet": add_subnet(actor, read_text(data, "network"), read_text(data, "name"),
                                       None if vlan is KEEP else vlan, read_text(data, "router") or None,
                                       read_strings(data, "pools"), read_text(data, "notes"),
                                       read_text(data, "allow_overlap"), source="web")}
    elif sub == ["subnets", "update"]:
        fields = {k: (read_text(data, k) if k in data else KEEP)
                  for k in ("name", "router", "notes", "allow_overlap")}
        result = {"subnet": update_subnet(actor, read_text(data, "subnet"), vlan=_vlan(data),
                                          add_pools=read_strings(data, "add_pools"),
                                          remove_pools=read_strings(data, "remove_pools"), source="web", **fields)}
    elif sub == ["subnets", "delete"]:
        try:
            leases = list_leases(load_vars())
        except ValidationError:
            leases = None
        result = {"removed": remove_subnet(actor, read_text(data, "subnet"), leases, bool(data.get("force")),
                                           source="web")}
    elif sub == ["options"]:
        label, option = set_option(actor, read_text(data, "option"), read_text(data, "data"),
                                   always_send=True if data.get("always_send") is True else None, source="web",
                                   **_where(data))
        result = {"where": label, "option": option}
    elif sub == ["options", "delete"]:
        result = {"where": unset_option(actor, read_text(data, "option"), source="web", **_where(data))}
    elif sub == ["classes"]:
        result = {"class": add_client_class(actor, read_text(data, "name"), read_text(data, "test"),
                                            read_text(data, "next_server") or None,
                                            read_text(data, "boot_file") or None, source="web")}
    elif len(sub) == 3 and sub[0] == "classes" and sub[2] == "delete":
        remove_client_class(actor, sub[1], source="web")
        result = {}
    else:
        raise RouteNotFound()
    ok, output = apply_changes(actor, source="web")
    return {**result, "applied": ok, "output": output[-2000:]}
