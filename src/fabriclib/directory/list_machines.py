from fabriclib.directory.run_op import run_op
from fabriclib.secrets.load_secrets import load_secrets


def list_machines(v, secrets=None, container="samba"):
    """Purpose: this site's machines in the domain (manual 2.10.2.6, 2.11.2.21 S7.4), Windows and Linux alike.
    Inputs:  v — fabric vars (site_name); secrets — fabric's secrets (default: load_secrets()); container — the DC's
             container (tests name their own).
    Returns: list of {"name", "dns", "os", "enabled", "last_logon", "created", "dn"}, sorted by name.
    Fails:   ValidationError from run_op (the DC not reachable or refusing) or load_secrets.
    Feeds:   samba/domain_overview (the Directory tab's Machines)."""
    return run_op(v, secrets if secrets is not None else load_secrets(), "list_machines", container=container)
