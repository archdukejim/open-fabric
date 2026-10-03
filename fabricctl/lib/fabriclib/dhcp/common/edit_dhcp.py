import copy

from fabriclib.common.jinja_env import jinja_env
from fabriclib.common.load_vars import load_vars
from fabriclib.common.save_vars import save_vars
from fabriclib.common.vars_lock import vars_lock
from fabriclib.common.write_audit import write_audit
from fabriclib.deploy.deploy_paths import deploy_paths
from fabriclib.dhcp.check_kea_config import check_kea_config
from fabriclib.dhcp.normalize_dhcp import normalize_dhcp


def edit_dhcp(actor, event, change, source="cli"):
    """Purpose: one change to `dhcp:` in vars.yaml, the way every DHCP command makes it: under the vars lock, on
             the normalized settings (so every subnet keeps a stored id), the whole block checked again — by fabric
             and, when DHCP is on, by Kea itself on the configuration it would get — before it is saved, then
             audited. Applied by the next apply.
    Inputs:  actor — who asks (audit); event — the audit event (e.g. "DHCP_SUBNET_ADD"); change — function(dhcp)
             that changes the dict in place and returns (result, audit detail str); source — "cli" or "web".
    Returns: (result of change, the saved dhcp block).
    Fails:   ValidationError from change, normalize_dhcp or Kea's check (check_kea_config: an option Kea does not
             know, data that does not fit, a class expression it cannot parse) — nothing is saved then, so a
             refused change never breaks the next apply; OSError or yaml.YAMLError from vars_lock / load_vars /
             save_vars / write_audit.
    Feeds:   dhcp/add_subnet, update_subnet, remove_subnet, set_option, unset_option, add_client_class,
             remove_client_class."""
    with vars_lock():
        data = load_vars()
        dhcp = normalize_dhcp({**data, "dhcp": copy.deepcopy(data.get("dhcp") or {}), "install_kea": True})
        result, detail = change(dhcp)
        data["dhcp"] = normalize_dhcp({**data, "dhcp": dhcp, "install_kea": True})
        if data.get("install_kea"):         # vars.yaml holds the rendered settings: render Kea's file from them
            text = jinja_env(deploy_paths()["jinja"]).get_template("kea/kea-dhcp4.conf.j2").render(**data)
            check_kea_config(data.get("image_kea", "fabric/kea:local"), "kea-dhcp4.conf", text)
        save_vars(data)
    write_audit(actor, event, detail, source)
    return result, data["dhcp"]
