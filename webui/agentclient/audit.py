from webui.agentclient.connection import call_agent
from webui.agentclient.errors import AgentError, ValidationError


def audit(actor, action, detail):
    """Purpose: Write a login event to the audit log, best effort so an agent outage never blocks a denial.
             Agent route: POST /v1/events (session).
    Inputs:  actor — str user name, or None/"" (sent as "unknown"); action — "LOGIN", "LOGOUT" or "LOGIN_DENIED"
             (the agent refuses others with 400); detail — str (the agent keeps 200 chars).
    Returns: None.
    Fails:   AgentError and ValidationError are swallowed; AuthError (401) and PermissionDenied (403) are not caught
             and propagate to Handler.handle_request (redirect to /login, or a 403 page).
    Feeds:   — (result unused); called by webui/session/finish_login (LOGIN, LOGIN_DENIED) and Handler.post
             for /logout (LOGOUT).
    """
    try:
        call_agent("POST", "/v1/events", {"actor": actor or "unknown", "action": action, "detail": detail})
    except (AgentError, ValidationError):
        pass
