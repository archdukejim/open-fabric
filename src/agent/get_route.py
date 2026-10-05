import os

from agent.route_not_found import RouteNotFound
from fabriclib.common.load_vars import load_vars
from fabriclib.common.read_audit import read_audit
from fabriclib.consent.consent_status import consent_status
from fabriclib.dhcp.dhcp_overview import dhcp_overview
from fabriclib.dns.list_tsig_keys import list_tsig_keys
from fabriclib.dns.list_zones import list_zones
from fabriclib.dns.reverse_zones import reverse_zones
from fabriclib.dns.zone_detail import zone_detail
from fabriclib.directory.device_overview import device_overview
from fabriclib.directory.list_people import list_people
from fabriclib.pki.ca_summary import ca_summary
from fabriclib.pki.list_issued import list_issued
from fabriclib.radius.radius_guides import radius_guides
from fabriclib.radius.radius_overview import radius_overview
from fabriclib.system.service_status import service_status
from fabriclib.system.version_info import version_info
from fabriclib.vault.detect_devices import detect_devices
from fabriclib.vault.list_slots import list_slots
from fabriclib.vault.vault_status import vault_status
from fabriclib.system.relaxed_settings import relaxed_settings

# GET /v1/<route> -> the read operation answering it (vars are read per request)
READS = {
    ("version",): lambda: version_info(),
    ("services",): lambda: service_status(),
    ("host-changes",): lambda: consent_status(os.path.join(load_vars()["deploy_base_dir"], "fabric", "config")),
    ("relaxed-settings",): lambda: relaxed_settings(load_vars()),
    ("zones",): lambda: list_zones(),
    ("audit",): lambda: read_audit(),
    ("pki", "ca"): lambda: ca_summary(load_vars()),
    ("pki", "issued"): lambda: list_issued(),
    ("tsig",): lambda: list_tsig_keys(),
    ("reverse-zones",): lambda: reverse_zones(load_vars()),
    ("devices",): lambda: device_overview(load_vars()),
    ("people",): lambda: list_people(load_vars()),
    ("dhcp",): lambda: dhcp_overview(load_vars()),
    ("radius",): lambda: radius_overview(load_vars()),
    ("radius", "guides"): lambda: radius_guides(load_vars()),
    ("vault",): lambda: vault_status(load_vars()),
    ("vault", "devices"): lambda: detect_devices(v=load_vars()),
}


def get_route(route):
    """Purpose: answer GET /v1/<route>: one fabriclib read operation per route.
    Inputs:  route — list of path segments after /v1/ (already authorized by the handler).
    Returns: the operation's JSON-serialisable result. zones/<key>: zone_detail; vault/slots: the unlock methods with
             this host's name.
    Fails:   RouteNotFound for any other route (-> 404); whatever the operation raises (ValidationError -> 400).
    Feeds:   agent/handler.py (dispatch)."""
    if tuple(route) in READS:
        return READS[tuple(route)]()
    if len(route) == 2 and route[0] == "zones":
        return zone_detail(route[1])
    if route == ["vault", "slots"]:
        v = load_vars()
        return {"slots": list_slots(v), "host": v.get("hostname", "")}
    raise RouteNotFound()
