from fabriclib.directory.run_op import run_op
from fabriclib.secrets.load_secrets import load_secrets


def read_address_plan(v, secrets=None, container="samba"):
    """Purpose: the address plan across sites, from the domain (manual 2.2.2.8, S4.2): every site's networks with
             name, VLAN, kind and notes, as convergence wrote them in each site's OU=networks.
    Inputs:  v — fabric vars (site_name); secrets — fabric's secrets (default: load_secrets()); container — the DC's
             container (tests name their own).
    Returns: list of {"site", "name", "cidr", "vlan", "kind", "notes", "allow_overlap"}, sorted by site and
             network; [] before any site has converged.
    Fails:   ValidationError from run_op (the DC not reachable) or load_secrets.
    Feeds:   federation/show_networks (`fabricctl federation networks`), dhcp/common/edit_dhcp and accept_join
             (overlap checks)."""
    return run_op(v, secrets if secrets is not None else load_secrets(), "read_networks", container=container)
