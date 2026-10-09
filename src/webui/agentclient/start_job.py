from webui.agentclient.connection import call_agent


def start_job(kind, body=None):
    """Purpose: start a background job in fabric-agent (manual 1.3.3): doctor's checks, or one service's image update
             or rollback. Agent routes: POST /v1/jobs/doctor (status:read), POST /v1/jobs/images (images:update; body:
             action update|rollback, service).
    Inputs:  kind — "doctor" or "images"; body — dict for images.
    Returns: str, the job's id (read it with read_job).
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403); KeyError if a 200 reply had no "id".
    Feeds:   src/webui/routes/overview_post.
    """
    return call_agent("POST", f"/v1/jobs/{kind}", body or {})["id"]
