import base64
import os
import urllib.parse

from webui import views
from webui.devpreview.sample_data import RECORD_TYPES


def dev_post_dns(h, path, form):
    """Purpose: TSIG keys and zone records acted out in memory (secrets are fresh random throwaways).
    Inputs:  h — the dev handler (send, state, ctx); path — /bind9/tsig/create, /bind9/tsig/<name>/rotate|delete,
             /bind9/zone/<key>/add|delete; form — dict.
    Returns: True when the path was handled; None otherwise.
    Fails:   ValueError for a non-numeric record index; IndexError for an unexpected …/rotate path (not caught).
    Feeds:   dev_post_action."""
    state = h.state
    if path == "/bind9/tsig/create" or path.endswith("/rotate"):
        name = form.get("name", "") if path.endswith("create") else path.split("/")[3]
        secret = base64.b64encode(os.urandom(32)).decode()
        ini = (f"# RFC2136 credentials for TSIG key: {name}\ndns_rfc2136_server = 192.168.1.53\n"
               f"dns_rfc2136_port = 53\ndns_rfc2136_name = {name}\ndns_rfc2136_secret = {secret}\n"
               f"dns_rfc2136_algorithm = HMAC-SHA256\ndns_rfc2136_base_domain = {form.get('zone') or 'home.arpa'}\n")
        if path.endswith("create") and name:
            state.data["tsig"].append({"name": name, "algorithm": "hmac-sha256", "types": "TXT",
                                       "scope": f"(dev preview) {form.get('scope', '')}", "acls": []})
        state.log("TSIG_ADD" if path.endswith("create") else "TSIG_SECRET", f"key={name} (in memory)")
        h.send(200, views.tsig_result(h.ctx, name or "preview", secret, ini,
                                      "created" if path.endswith("create") else "rotated"))
        return True
    if path.startswith("/bind9/tsig/") and path.endswith("/delete"):
        name = path.split("/")[3]
        state.data["tsig"] = [k for k in state.data["tsig"] if k["name"] != name]
        h.send(303, b"", location="/bind9?view=tsig&msg=" +
               urllib.parse.quote(f"TSIG key {name} removed (dev preview: in memory)."))
        return True
    parts = path.strip("/").split("/")
    if not (len(parts) == 4 and parts[:2] == ["bind9", "zone"] and parts[2] in state.data["zones"]):
        return None
    key, op = parts[2], parts[3]
    records = state.data["zones"][key]["records"]
    if op == "add":
        rtype, name = form.get("type", ""), form.get("name", "").strip()
        value = next((form.get(f, "").strip() for f in ("ip", "target", "text") if form.get(f, "").strip()), "")
        if rtype not in RECORD_TYPES or not name or not value:
            h.send(303, b"", location=f"/bind9?zone={urllib.parse.quote(key)}&err=" +
                   urllib.parse.quote("type, name and a value are required"))
            return True
        records.append((rtype, name, value))
        state.log("DNS_ADD", f"zone={key} {rtype} {name} {value} (in memory)")
        msg = "Record added (dev preview: in memory only)."
    elif op == "delete":
        idx = int(form.get("index", -1))           # position in the zone's list (DevState.zone)
        if 0 <= idx < len(records) and records[idx][0] == form.get("type"):
            removed = records.pop(idx)
            state.log("DNS_DELETE", f"zone={key} {removed[0]} {removed[1]} (in memory)")
        msg = "Record deleted (dev preview: in memory only)."
    else:
        h.send(404, views.error_page(404, "Not found."))
        return True
    h.send(303, b"", location=f"/bind9?zone={urllib.parse.quote(key)}&msg=" + urllib.parse.quote(msg))
    return True
