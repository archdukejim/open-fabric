import json
import os
import subprocess

from fabriclib.common.errors import ValidationError
from fabriclib.federation.site_networks import site_networks
from fabriclib.ldap.people_written_here import people_written_here


def converge_domain(v, federation_file, container="samba"):
    """Purpose: bring the domain to what fabric wants (manual 2.11.2.15, S1.3): hand the wanted state to the converge
             code inside the running DC (src/containers/samba/converge.py) and return what it changed. Every part is
             idempotent, so it runs after every start and apply.
    Inputs:  v — rendered vars: site_name, ad_password_policy, deploy_base_dir (the root CA under
             stepca/data/certs), lan_cidr and the DHCP subnets (site_networks); federation_file — the federation
             registry (whether this is the root site); container — the DC's container (tests name their own).
    Returns: list of str, what changed (empty when the domain already was as wanted).
    Fails:   ValidationError when the DC is not running or the converge code reports an error (its message);
             OSError reading the root CA; subprocess.TimeoutExpired after 10 minutes.
    Feeds:   setup/start_services (after the DC starts), deploy/restart_changed (every apply), tests/samba."""
    root_ca = os.path.join(v["deploy_base_dir"], "stepca", "data", "certs", "root_ca.crt")
    state = {"site": v["site_name"], "root": people_written_here(federation_file),
             "password_policy": v["ad_password_policy"],
             "networks": [n["cidr"] for n in site_networks(v)],
             "root_ca_pem": open(root_ca).read()}
    res = subprocess.run(["docker", "exec", "-i", "-e", "PYTHONDONTWRITEBYTECODE=1", container,
                          "python3", "/fabric/converge.py"],
                         input=json.dumps(state), capture_output=True, text=True, timeout=600)
    if res.returncode != 0:
        raise ValidationError("the Windows domain could not be converged: "
                              + ((res.stderr or res.stdout).strip().splitlines() or ["the DC is not running"])[-1])
    return json.loads(res.stdout)["changed"]
