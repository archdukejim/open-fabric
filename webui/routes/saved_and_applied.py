import urllib.parse

from webui import agentclient as actions


def saved_and_applied(h, tab, change):
    """Purpose: Run a change that fabric-agent saves and applies at once, and go back to its tab with the outcome.
    Inputs:  h — the request handler (redirect, deny); tab — the page to go back to (/kea, /freeradius); change — a
             function returning (agent result with "applied" and "output", the message to show), or None for an
             unknown path.
    Returns: 303 to the tab with msg; with err when applying failed (the last 300 characters of its output) or the agent
             refused the input; 404 when change returned None.
    Fails:   AgentError, PermissionDenied and AuthError propagate to handle_request.
    Feeds:   post_action (Kea reservations, FreeRADIUS people)."""
    try:
        done = change()
        if done is None:
            return h.deny(404, "Not found.")
        res, msg = done
        if not res.get("applied"):
            return h.redirect(f"{tab}?" + urllib.parse.urlencode(
                {"err": msg + " Saved, but applying failed: " + res.get("output", "")[-300:]}))
    except actions.ValidationError as exc:
        return h.redirect(f"{tab}?" + urllib.parse.urlencode({"err": str(exc)}))
    return h.redirect(f"{tab}?" + urllib.parse.urlencode({"msg": msg}))
