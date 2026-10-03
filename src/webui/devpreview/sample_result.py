import base64
import secrets

from webui.devpreview.sample_data import SAMPLE_INFO, SAMPLE_KEY, SAMPLE_PEM


def sample_result(kind):
    """Purpose: A fake PKI result for the sign/issue/convert result page, shaped like fabric-agent's reply.
    Inputs:  kind — "sign", "issue" or "convert"; "issue" adds a key and .p12, "convert" adds .p7b and .p12;
             anything else gets the base fields only.
    Returns: {"name", "cert", "fullchain", "der_b64", "info"} plus the kind's extras; certificates and keys are
             placeholder text, p12_password is a fresh random token.
    Fails:   never.
    Feeds:   Handler.do_POST for /stepca/sign, /stepca/issue and /stepca/convert (views.pki_result).
    """
    b64 = base64.b64encode(SAMPLE_PEM.encode()).decode()
    r = {"name": "device.home.arpa", "cert": SAMPLE_PEM, "fullchain": SAMPLE_PEM * 3, "der_b64": b64,
         "info": SAMPLE_INFO}
    if kind == "issue":
        r.update(key=SAMPLE_KEY, p12_b64=b64, p12_password=secrets.token_urlsafe(15))
    if kind == "convert":
        r.update(p7b_b64=b64, p12_b64=b64, p12_password=secrets.token_urlsafe(15))
    return r
