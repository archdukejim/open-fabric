import urllib.parse

from webui import views
from webui.devpreview.sample_data import SAMPLE_DHCP, SAMPLE_RADIUS


def dev_post_network(h, path, form):
    """Purpose: RADIUS groups and clients and Kea reservations, acted out on the sample data in memory.
    Inputs:  h — the dev handler (send, ctx); path — /freeradius/people…, /freeradius/clients…, /kea/reservations…;
             form — dict.
    Returns: True when the path was handled (a 303 with msg, or the shared-secret page); None otherwise.
    Fails:   ValueError for a non-numeric vlan or priority (not caught: http.server closes the connection).
    Feeds:   dev_post_action."""
    if path.startswith("/freeradius/people"):
        parts = [urllib.parse.unquote(p) for p in path.split("/")[3:]]
        people = SAMPLE_RADIUS["people"]
        if parts:
            people[:] = [m for m in people if m["group"] != parts[0]]
            msg = f"Members of {parts[0]} may no longer join by password (dev preview)."
        else:
            people.append({"group": form.get("group", ""), "vlan": int(form["vlan"]) if form.get("vlan") else None,
                           "priority": int(form.get("priority") or 100)})
            msg = f"Members of {form.get('group', '')} may join by password (dev preview)."
        h.send(303, b"", location="/freeradius?" + urllib.parse.urlencode({"msg": msg}))
        return True
    if path.startswith("/freeradius/clients"):
        parts = [urllib.parse.unquote(p) for p in path.split("/")[3:]]
        clients = SAMPLE_RADIUS["clients"]
        if len(parts) == 2 and parts[1] == "delete":
            clients[:] = [c for c in clients if c["name"] != parts[0]]
            h.send(303, b"", location="/freeradius?" + urllib.parse.urlencode(
                {"msg": f"RADIUS client {parts[0]} removed (dev preview)."}))
            return True
        name = parts[0] if parts else form.get("name", "").lower()
        if not parts:
            clients.append({"name": name, "address": form.get("address", ""),
                            "message_authenticator": form.get("message_authenticator") == "1"})
        h.send(200, views.radius_secret(h.ctx, name, "dev-preview-not-a-real-secret",
                                        "added" if not parts else "rotated", "192.168.1.2"))
        return True
    if path.startswith("/kea/reservations"):
        rs = SAMPLE_DHCP["subnets"][0]["reservations"]
        parts = path.split("/")[3:]
        if not parts:
            rs.append({"mac": form.get("mac", "").lower(), "ip": form.get("ip", ""), "hostname": form.get("hostname", "")})
            msg = f"Reserved {form.get('ip', '')} (dev preview: nothing applied)."
        else:
            rs[:] = [r for r in rs if r["mac"] != urllib.parse.unquote(parts[0])]
            msg = "Reservation removed (dev preview)."
        h.send(303, b"", location="/kea?" + urllib.parse.urlencode({"msg": msg}))
        return True
    return None
