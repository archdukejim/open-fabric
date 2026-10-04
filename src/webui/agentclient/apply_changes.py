from webui.agentclient.connection import call_agent


def apply_changes(actor):
    """Purpose: Render and apply the configuration (as `fabricctl --apply`) on the host.
             Agent route: POST /v1/apply (dns:write), timeout 960 s.
    Inputs:  actor — str user name (ignored by the agent for token callers).
    Returns: (ok: bool, output: str) — whether the apply succeeded and its log output.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             a failed apply is ok=False, not an exception.
    Feeds:   src/webui/routes/post_action for "/apply" (views.apply_result).
    """
    result = call_agent("POST", "/v1/apply", {"actor": actor}, timeout=960)
    return result["ok"], result["output"]
