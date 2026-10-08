from fabriclib.directory.run_op import run_op
from fabriclib.secrets.load_secrets import load_secrets


def list_people(v, secrets=None):
    """Purpose: the People page (manual 1.6.3): every person and group in the directory, read as this site's agent;
             never a password.
    Inputs:  v — fabric vars (site_name; hostname_keycloak and webui_realm or domain for the link); secrets — fabric's
             secrets (default: load_secrets()).
    Returns: {"users": [{uid, name, mail, locked, groups, site, uidNumber}], "groups": [{name, members}],
              "keycloak_url": the realm's admin console}.
    Fails:   ValidationError from run_op (the directory unreachable) or load_secrets (OpenBao sealed).
    Feeds:   agent route GET /v1/people -> webui agentclient.list_people -> People page."""
    out = run_op(v, secrets if secrets is not None else load_secrets(), "list_people")
    realm = v.get("webui_realm") or v["domain"]
    out["keycloak_url"] = f"https://{v['hostname_keycloak']}/admin/{realm}/console/"
    return out
