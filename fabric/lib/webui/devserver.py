#!/usr/bin/env python3
"""Fabric web UI — DEV PREVIEW. The real pages (views.py) with sample data:
no sign-in, no client certificate, no fabric-agent, nothing saved or
applied. Record edits live in memory until the process stops.

A separate entry point on purpose: the production server (server.py) has no
dev switch, so this can never be turned on in a real install.

  python3 fabric/lib/webui/devserver.py                      # http://127.0.0.1:8080
  docker run --rm -p 127.0.0.1:8080:8080 --entrypoint /usr/bin/python3 \\
      fabric/webui:local /app/webui/devserver.py --bind 0.0.0.0   # from the image
"""
import argparse
import copy
import os
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from webui import views  # noqa: E402

RECORD_TYPES = ["A", "AAAA", "CNAME", "MX", "TXT", "SRV"]
SAMPLE = {
    "services": [("nginx", "active", "healthy"), ("bind9", "active", "healthy"), ("stepca", "active", "healthy"),
                 ("ldap", "active", "healthy"), ("postgres", "active", "healthy"), ("keycloak", "active", "healthy"),
                 ("openbao", "active", "healthy"), ("webui", "active", "healthy"), ("fabric-agent", "active", "")],
    "zones": {
        "dynamic_zone_var": {"name": "home.arpa", "records": [
            ("A", "fabric", "192.168.1.53"), ("A", "@", "192.168.1.53"), ("A", "nas", "192.168.1.10"),
            ("CNAME", "ca", "fabric"), ("CNAME", "certs", "fabric"), ("CNAME", "dns", "fabric"),
            ("CNAME", "sso", "fabric"), ("MX", "@", "10 mail"), ("TXT", "@", '"v=spf1 -all"')]},
        "1.168.192.in-addr.arpa": {"name": "1.168.192.in-addr.arpa", "records": [
            ("PTR", "53", "fabric.home.arpa.")]},
    },
    "audit": ["[dev] User: dev (web) | Action: LOGIN | dev preview — no certificate, no Keycloak\n"],
}


class DevState:
    """In-memory sample data; nothing leaves this process."""

    def __init__(self):
        self.data = copy.deepcopy(SAMPLE)
        self.lock = threading.Lock()

    def zones(self):
        return [{"key": k, "name": z["name"], "records": len(z["records"])} for k, z in self.data["zones"].items()]

    def zone(self, key):
        z = self.data["zones"][key]
        return {"key": key, "name": z["name"], "status": "dev preview — sample data, not served by BIND",
                "records": [{"type": t, "index": i, "name": n, "value": v} for i, (t, n, v) in enumerate(z["records"])]}

    def log(self, action, detail):
        self.data["audit"].insert(0, f"[dev] User: dev (web) | Action: {action} | {detail}\n")


class Handler(BaseHTTPRequestHandler):
    state = DevState()
    ctx = {"user": "dev (preview)", "csrf": "dev", "dev": True,
           "version": {"version": "dev preview", "build": "sample data · no sign-in · nothing is saved"}}

    def log_message(self, fmt, *args):
        pass

    def send(self, status, body, ctype="text/html; charset=utf-8", location=None):
        data = body.encode() if isinstance(body, str) else body
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'self'; form-action 'self'")
        if location:
            self.send_header("Location", location)
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
        query = dict(urllib.parse.parse_qsl(urllib.parse.urlsplit(self.path).query))
        with self.state.lock:
            if path == "/static/app.css":
                return self.send(200, views.css(), "text/css; charset=utf-8")
            if path == "/":
                return self.send(200, views.overview(self.ctx, self.state.data["services"]))
            if path == "/bind9":
                key = query.get("zone") or next(iter(self.state.data["zones"]))
                zone = self.state.zone(key) if key in self.state.data["zones"] else None
                return self.send(200, views.bind9(self.ctx, self.state.zones(), zone, RECORD_TYPES,
                                                  query.get("msg", ""), query.get("err", "")))
            if path.lstrip("/") in views.PLACEHOLDERS:
                return self.send(200, views.placeholder(self.ctx, path.lstrip("/")))
            if path == "/audit":
                return self.send(200, views.audit(self.ctx, self.state.data["audit"]))
            if path == "/preview/denied":       # what a refused sign-in looks like
                return self.send(403, views.error_page(403, "Your account is missing the 'fabric-admin' role."))
            return self.send(404, views.error_page(404, "Not found."))

    def do_POST(self):
        path = urllib.parse.unquote(urllib.parse.urlsplit(self.path).path)
        length = min(int(self.headers.get("Content-Length") or 0), 65536)
        form = dict(urllib.parse.parse_qsl(self.rfile.read(length).decode(errors="replace")))
        with self.state.lock:
            if path == "/logout":
                return self.send(303, b"", location="/")
            if path == "/apply":
                self.state.log("APPLY", "dev preview: nothing applied")
                return self.send(200, views.apply_result(self.ctx, True,
                                                         "DEV PREVIEW — nothing was rendered or reloaded.\n"
                                                         "On a real install this runs `fabricctl --apply`."))
            parts = path.strip("/").split("/")
            if len(parts) == 4 and parts[:2] == ["bind9", "zone"] and parts[2] in self.state.data["zones"]:
                key, op = parts[2], parts[3]
                records = self.state.data["zones"][key]["records"]
                if op == "add":
                    rtype, name = form.get("type", ""), form.get("name", "").strip()
                    value = next((form.get(f, "").strip() for f in ("ip", "target", "text") if form.get(f, "").strip()), "")
                    if rtype not in RECORD_TYPES or not name or not value:
                        return self.send(303, b"", location=f"/bind9?zone={urllib.parse.quote(key)}&err=" +
                                         urllib.parse.quote("type, name and a value are required"))
                    records.append((rtype, name, value))
                    self.state.log("DNS_ADD", f"zone={key} {rtype} {name} {value} (in memory)")
                    msg = "Record added (dev preview: in memory only)."
                elif op == "delete":
                    idx = int(form.get("index", -1))           # position in the zone's list (DevState.zone)
                    if 0 <= idx < len(records) and records[idx][0] == form.get("type"):
                        removed = records.pop(idx)
                        self.state.log("DNS_DELETE", f"zone={key} {removed[0]} {removed[1]} (in memory)")
                    msg = "Record deleted (dev preview: in memory only)."
                else:
                    return self.send(404, views.error_page(404, "Not found."))
                return self.send(303, b"", location=f"/bind9?zone={urllib.parse.quote(key)}&msg=" + urllib.parse.quote(msg))
            return self.send(404, views.error_page(404, "Not found."))


def main():
    ap = argparse.ArgumentParser(description="Fabric web UI dev preview (sample data, no sign-in, no backend)")
    ap.add_argument("--bind", default="127.0.0.1", help="address to listen on (default 127.0.0.1)")
    ap.add_argument("--port", type=int, default=8080)
    args = ap.parse_args()
    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    print(f"Fabric web UI DEV PREVIEW on http://{args.bind}:{args.port}/ — sample data, no sign-in, "
          "nothing is saved. Never expose this.", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
