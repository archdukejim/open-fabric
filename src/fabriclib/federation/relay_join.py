from fabriclib.common.errors import ValidationError
from fabriclib.common.write_audit import write_audit
from fabriclib.federation.common.load_registry import load_registry
from fabriclib.federation.common.post_upstream import post_upstream
from fabriclib.pki.common.ca_files import ca_files

PREFIX = "the upstream refused: "


def relay_join(v, req, client_ip=""):
    """Purpose: on a relay node (a site named in an invitation's --via): pass a join on to this site's upstream —
             the root, over TLS verified against the organisation's root — and hand its answer back unchanged
             (manual 1.9.5.1). The node signs nothing and decides nothing.
    Inputs:  v — fabric vars: site_name, deploy_base_dir (the root certificate); req — the join request; it must
             name this site in "via"; client_ip — str for the audit.
    Returns: the upstream's answer (dict), as accept_join returned it there.
    Fails:   ValidationError "this site is not the relay named in the request"; "this site has no upstream to
             relay to"; the upstream's own refusal message (e.g. an expired invitation) passed through;
             post_upstream's "cannot reach the upstream's federation endpoint ..."; OSError reading the root.
    Feeds:   the federation endpoint (lib/federation/server.py, POST /v1/join with "via").
    Notes:   the node terminates TLS, so it sees the request — the CSR and the invitation's one-time secret —
             before passing it on; both are single-use and consumed by the root. Audited as FED_JOIN_RELAYED."""
    if not isinstance(req, dict) or req.get("via") != v.get("site_name"):
        raise ValidationError("this site is not the relay named in the request")
    up = load_registry()["upstream"]
    if not up:
        raise ValidationError("this site has no upstream to relay to")
    with open(ca_files(v)[0]) as f:
        root = f.read()
    try:
        answer = post_upstream(up["address"], up["host"], root, "/v1/join", req, port=int(up.get("port") or 443))
    except ValidationError as e:
        msg = str(e)
        raise ValidationError(msg[len(PREFIX):] if msg.startswith(PREFIX) else msg) from None
    write_audit(f"site:{req.get('site', '?')}", "FED_JOIN_RELAYED",
                f"site={req.get('site', '?')} to={up.get('site_name')} from={client_ip}", "federation")
    return answer
