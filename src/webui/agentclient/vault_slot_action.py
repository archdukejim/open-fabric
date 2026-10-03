from webui.agentclient.connection import call_agent
from webui.agentclient.quote_segment import quote_segment


def vault_slot_action(actor, slot_id, op):
    """Purpose: Test or remove one unlock method.
             Agent route: POST /v1/vault/slots/<id>/<op> (vault:unlock), timeout 120 s.
    Inputs:  actor — str user name; slot_id — slot id (quoted); op — "test" or "remove", put in the path unquoted
             (the caller only passes those two).
    Returns: {"ok": bool}.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError when fabriclib refuses (e.g. the test fails, the last method); another op is
             not in the route table -> PermissionDenied.
    Feeds:   src/webui/routes/vault_post.
    """
    return call_agent("POST", f"/v1/vault/slots/{quote_segment(slot_id)}/{op}", {"actor": actor}, timeout=120)
