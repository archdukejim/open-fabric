from webui.agentclient.connection import call_agent
from webui.agentclient.quote_segment import quote_segment


def read_job(job_id):
    """Purpose: a background job the signed-in person started: running, done (with its result) or failed (with why).
             Agent route: GET /v1/jobs/<id> (any signed-in person; only their own jobs).
    Inputs:  job_id — str.
    Returns: {"id", "kind", "state", "started", "result", "error"}.
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400: no such job, or
             another person's), AuthError (401), PermissionDenied (403).
    Feeds:   src/webui/routes/get_page for /jobs/<id> (views.job_page).
    """
    return call_agent("GET", f"/v1/jobs/{quote_segment(job_id)}")
