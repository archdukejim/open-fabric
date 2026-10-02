from webui.agentclient.connection import call_agent


def create_person(uid, first, last, email):
    """Purpose: Create a person in Keycloak with a one-time password.
             Agent route: POST /v1/people (people:create).
    Inputs:  uid — user name; first, last — names; email — address. No actor: the agent uses the token's user.
    Returns: str one-time password (shown once, stored nowhere).
    Fails:   the call_agent exceptions: AgentError (down/timeout/other status), ValidationError (400), AuthError (401),
             PermissionDenied (403);
             ValidationError for bad or duplicate values; KeyError if a 200 reply had no "password".
    Feeds:   webui/routes/dirsrv_post (people/_new -> views.person_result).
    """
    return call_agent("POST", "/v1/people", {"uid": uid, "first": first, "last": last, "email": email})["password"]
