import urllib.parse

from webui import views
from webui.devpreview.dev_post_directory import dev_post_directory
from webui.devpreview.dev_post_dns import dev_post_dns
from webui.devpreview.dev_post_dhcp import dev_post_dhcp
from webui.devpreview.dev_post_network import dev_post_network
from webui.devpreview.sample_data import SAMPLE_CA, SAMPLE_INFO, SAMPLE_PEM
from webui.devpreview.sample_result import sample_result


def dev_post_action(h, path, form):
    """Purpose: Act out every form post in memory only (DNS records, TSIG keys, apply, PKI, vault, devices, roles,
             people, DHCP reservations, RADIUS clients and groups) and show the same result page or redirect as
             production. Nothing is saved, signed or applied; secrets and passwords shown are fake or throwaway.
    Inputs:  h — the dev handler (send, state, ctx); path — the URL path; form — dict (text fields only).
    Returns: None; sends 200 result pages, 303 redirects carrying msg/err, or 404 for an unknown route.
    Fails:   errors other than the directory's ValidationError are not caught: http.server logs them and closes the
             connection.
    Feeds:   dev_handler.DevHandler.do_POST (under the state lock)."""
    state, ctx = h.state, h.ctx
    if path == "/logout":
        return h.send(303, b"", location="/")
    if path == "/apply":
        state.log("APPLY", "dev preview: nothing applied")
        return h.send(200, views.apply_result(ctx, True, "DEV PREVIEW — nothing was rendered or reloaded.\n"
                                                         "On a real install this runs `fabricctl --apply`."))
    if path.startswith("/openbao/"):
        return h.send(303, b"", location="/openbao?" + urllib.parse.urlencode(
            {"view": "unlock", **state.vault_action(path.split("/")[2:], form)}))
    for area in (dev_post_dhcp, dev_post_network, dev_post_directory):
        if area(h, path, form):
            return None
    if path == "/stepca/sign/review":
        review = {"pem": SAMPLE_PEM, "subject": SAMPLE_INFO["subject"], "cn": "device.home.arpa",
                  "sans": SAMPLE_INFO["sans"], "key": "RSA 2048", "ca_requested": False, "problems": [],
                  "text": "DEV PREVIEW — a real install shows the decoded request here."}
        return h.send(200, views.stepca(ctx, "sign", SAMPLE_CA, review=review))
    if path == "/stepca/inspect":
        item = {"info": SAMPLE_INFO, "trusted": True, "text": "DEV PREVIEW — a real install shows `openssl x509 -text` here."}
        return h.send(200, views.stepca(ctx, "inspect", SAMPLE_CA, inspected={"kind": "cert", "items": [item]}))
    if path in ("/stepca/sign", "/stepca/issue", "/stepca/convert"):
        kind = path.rsplit("/", 1)[1]
        state.log(f"PKI_{kind.upper()}", "dev preview: sample only, nothing signed")
        return h.send(200, views.pki_result(ctx, kind, sample_result(kind)))
    if dev_post_dns(h, path, form):
        return None
    return h.send(404, views.error_page(404, "Not found."))
