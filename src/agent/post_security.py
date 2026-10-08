from agent.read_text import read_text
from agent.route_not_found import RouteNotFound
from fabriclib.security.apply_signin import apply_signin
from fabriclib.security.set_signin_layer import set_signin_layer


def post_security(route, actor, data):
    """Purpose: the Security page's changes (manual 2.3.6.2.6.4, 2.1.6.24, 2.1.6.27): POST /v1/security/raise {layer,
             value} — only a raise (a lowering is refused here: it is done on the host with `fabricctl security lower`)
             — and POST /v1/security/kerberos {value: on|off}; each saved, audited and applied at once.
    Inputs:  route — segments after /v1/; actor — the verified user; data — the body.
    Returns: {"layer", "from", "to", "changed", "applied": bool, "output": the last 2000 characters}.
    Fails:   ValidationError from set_signin_layer (-> 400: a lowering, an unknown layer or value); RouteNotFound for
             another route.
    Feeds:   agent/post_route.py."""
    if route == ["security", "raise"]:
        res = set_signin_layer(actor, read_text(data, "layer"), read_text(data, "value"), "web")
    elif route == ["security", "kerberos"]:
        res = set_signin_layer(actor, "kerberos", read_text(data, "value"), "web")
    else:
        raise RouteNotFound()
    ok, output = apply_signin(actor, "web") if res["changed"] else (True, "")
    return {**res, "applied": ok, "output": output[-2000:]}
