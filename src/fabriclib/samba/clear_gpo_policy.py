from fabriclib.common.write_audit import write_audit
from fabriclib.samba.gpo_request import gpo_request


def clear_gpo_policy(v, actor, policy, source="cli", container="samba"):
    """Purpose: put one policy of this site's admin settings GPO back to "Not configured" (manual 3.15.4).
    Inputs:  v — fabric vars (site_name); actor — str, for the audit; policy — its name or title; source — audit
             source; container — the DC's container.
    Returns: list of str, what changed.
    Fails:   ValidationError from gpo_request (no such policy, the DC not running).
    Feeds:   samba/run_gpo_command (`fabricctl gpo clear`); agent route POST /v1/gpo/clear (gpo:admin).
    Notes:   audited as GPO_CLEAR."""
    site = v["site_name"]
    done = gpo_request({"op": "clear", "site": site, "policy": policy}, container)
    write_audit(actor, "GPO_CLEAR", f"site={site} policy={policy}", source)
    return done
