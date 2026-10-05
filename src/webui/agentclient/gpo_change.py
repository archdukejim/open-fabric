from webui.agentclient.connection import call_agent


def gpo_change(op, policy, values=None, enabled=True):
    """Purpose: Set or clear one policy in the site's admin settings GPO.
             Agent routes: POST /v1/gpo/set and /v1/gpo/clear (gpo:admin).
    Inputs:  op — "set" or "clear"; policy — its name or title; values — {element id: text} for set; enabled — False
             sets it to Disabled.
    Returns: list of str, what changed.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403).
             ValidationError for an unknown policy or a wrong value.
    Feeds:   src/webui/routes/directory_post (gpo).
    """
    body = {"policy": policy}
    if op == "set":
        body.update({"values": values or {}, "enabled": bool(enabled)})
    return call_agent("POST", f"/v1/gpo/{'set' if op == 'set' else 'clear'}", body)["changed"]
