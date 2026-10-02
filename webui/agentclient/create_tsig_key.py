from webui.agentclient.connection import call_agent


def create_tsig_key(actor, name, zone, scope, hosts, types, secret):
    """Purpose: Create a TSIG key allowed to update part of a zone (published by the next apply).
             Agent route: POST /v1/tsig (tsig:manage).
    Inputs:  actor — str user name; name — key name; zone — zone name; scope — str scope choice from the form;
             hosts — list of str host names; types — list of record types; secret — str, "" to generate one.
    Returns: {"key": key dict, "secret": str, "ini": str certbot RFC2136 credentials} — the secret is shown once.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for a bad or duplicate name, zone, scope, host or type.
    Feeds:   webui/routes/tsig_post (create -> views.tsig_result).
    """
    return call_agent("POST", "/v1/tsig", {"actor": actor, "name": name, "zone": zone, "scope": scope,
                                      "hosts": hosts, "types": types, "secret": secret})
