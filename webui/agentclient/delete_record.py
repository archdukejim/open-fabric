from webui.agentclient.connection import call_agent
from webui.agentclient.quote_segment import quote_segment


def delete_record(actor, key, rtype, index, expected_name):
    """Purpose: Remove one DNS record from a zone, only if it is still the record the page showed.
             Agent route: POST /v1/zones/<key>/records/delete (dns:write).
    Inputs:  actor — str user name (ignored by the agent for token callers); key — zone key; rtype — record type;
             index — int position among that type's records; expected_name — the name the page showed.
    Returns: the removed record (fabriclib.dns.remove_record).
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError if the index is out of range or the name no longer matches.
    Feeds:   webui/routes/post_action for /bind9/zone/<key>/delete (result unused).
    """
    return call_agent("POST", f"/v1/zones/{quote_segment(key)}/records/delete",
                 {"actor": actor, "type": rtype, "index": index, "name": expected_name})
