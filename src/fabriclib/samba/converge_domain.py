import json
import os
import subprocess

from fabriclib.common.errors import ValidationError
from fabriclib.federation.site_networks import site_networks
from fabriclib.ldap.people_written_here import people_written_here
from fabriclib.samba.id_range import id_range


def converge_domain(v, federation_file, secrets, container="samba"):
    """Purpose: bring the domain to what fabric wants (manual 2.11.2.15, S1.3): hand the wanted state to the converge
             code inside the running DC (src/containers/samba/converge.py) and return what it changed. Every part is
             idempotent, so it runs after every start and apply.
    Inputs:  v — rendered vars: site_name, ad_password_policy, deploy_base_dir (the root CA under
             stepca/data/certs), lan_cidr and the DHCP subnets (site_networks), ldap_groups, webui_admin_group,
             service_users (FreeRADIUS's gid), the id block (posix_id_block from the users OU's uid_range start);
             federation_file — the federation registry (whether this is the root site); secrets — fabric's secrets
             (the service accounts' passwords: ad_agent_password, ad_keycloak_password, ad_radius_password);
             container — the DC's container.
    Returns: list of str, what changed (empty when the domain already was as wanted).
    Fails:   ValidationError when the DC is not running or the converge code reports an error (its message);
             KeyError for a missing service-account secret;
             OSError reading the root CA; subprocess.TimeoutExpired after 10 minutes.
    Feeds:   setup/start_services (after the DC starts), deploy/restart_changed (every apply), tests/samba."""
    root_ca = os.path.join(v["deploy_base_dir"], "stepca", "data", "certs", "root_ca.crt")
    state = {"site": v["site_name"], "root": people_written_here(federation_file),
             "password_policy": v["ad_password_policy"],
             "networks": site_networks(v),
             "root_ca_pem": open(root_ca).read(), "id_range": id_range(v),
             "groups": [{"name": g["name"], "gidNumber": g["gidNumber"], "description": g.get("description", "")}
                        for g in v.get("ldap_groups") or []],
             "admin_group": v.get("webui_admin_group") or "admins",
             "accounts": {f"fabric-{kind}-{v['site_name']}": secrets[f"ad_{kind}_password"]
                          for kind in ("agent", "keycloak", "radius")},
             "radius_gid": v["service_users"]["freeradius"]["gid"]}
    res = subprocess.run(["docker", "exec", "-i", "-e", "PYTHONDONTWRITEBYTECODE=1", container,
                          "python3", "/fabric/converge.py"],
                         input=json.dumps(state), capture_output=True, text=True, timeout=600)
    if res.returncode != 0:
        raise ValidationError("the Windows domain could not be converged: "
                              + ((res.stderr or res.stdout).strip().splitlines() or ["the DC is not running"])[-1])
    return json.loads(res.stdout)["changed"]
