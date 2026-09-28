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
import base64
import copy
import os
import secrets
import sys
import threading
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from webui import views  # noqa: E402
try:        # the real PTR rules when run from a checkout; the webui image carries only webui/
    from fabriclib.dns.ptr_for_ip import ptr_for_ip  # noqa: E402
    from fabriclib.dns.reverse_zones import reverse_zones  # noqa: E402
except ImportError:
    ptr_for_ip = reverse_zones = None

RECORD_TYPES = ["A", "AAAA", "CNAME", "MX", "TXT", "SRV"]
SAMPLE = {
    "services": [("nginx", "active", "healthy"), ("bind9", "active", "healthy"), ("stepca", "active", "healthy"),
                 ("ldap", "active", "healthy"), ("postgres", "active", "healthy"), ("keycloak", "active", "healthy"),
                 ("openbao", "active", "healthy"), ("webui", "active", "healthy"), ("fabric-agent", "active", "")],
    "zones": {
        "dynamic_zone_var": {"name": "home.arpa", "records": [
            ("A", "fabric", "192.168.1.53"), ("A", "@", "192.168.1.53"), ("A", "nas", "192.168.1.10"),
            ("CNAME", "ca", "fabric"), ("CNAME", "certs", "fabric"), ("CNAME", "dns", "fabric"),
            ("A", "printer", "192.168.1.40"), ("AAAA", "nas", "fd00:1:2:3::10"), ("A", "vpn", "203.0.113.7"),
            ("CNAME", "ca", "fabric"), ("CNAME", "certs", "fabric"), ("CNAME", "dns", "fabric"),
            ("CNAME", "sso", "fabric"), ("MX", "@", "10 mail"), ("TXT", "@", '"v=spf1 -all"')]},
        "iot.home.arpa": {"name": "iot.home.arpa", "records": [
            ("A", "cam-front", "192.168.20.11"), ("A", "cam-back", "192.168.20.12"), ("A", "thermostat", "192.168.20.30")]},
    },
    "audit": ["[dev] User: dev (web) | Action: LOGIN | dev preview — no certificate, no Keycloak\n"],
    "tsig": [{"name": "npm-certbot", "algorithm": "hmac-sha256", "types": "TXT",
              "scope": "_acme-challenge.npm.home.arpa, _acme-challenge.nas.home.arpa", "acls": ["certbot-devices"]},
             {"name": "home.arpa-acme", "algorithm": "hmac-sha256", "types": "TXT",
              "scope": "_acme-challenge (zone home.arpa)", "acls": []}],
    "issued": [{"when": "2026-09-20T10:12:00", "actor": "dev", "kind": "csr", "subject": "CN=switch-core.home.arpa",
                "sans": ["switch-core.home.arpa", "192.168.1.2"], "not_after": "Sep 20 10:12:00 2027 GMT",
                "status": "valid"},
               {"when": "2025-10-01T08:00:00", "actor": "dev", "kind": "keypair", "subject": "CN=printer.home.arpa",
                "sans": ["printer.home.arpa"], "not_after": "Oct 15 08:00:00 2026 GMT", "status": "expires soon"}],
}
_FP = ":".join(["AB", "12", "CD", "34"] * 8)
SAMPLE_CA = {"certs_url": "http://certs.home.arpa/", "max_days": 1825,
             "root": {"subject": "CN=Fabric Root CA,O=Fabric", "not_after": "Sep  1 00:00:00 2046 GMT",
                      "key": "EC prime256v1", "sha256": _FP},
             "intermediate": {"subject": "CN=Fabric Intermediate CA,O=Fabric", "not_after": "Sep  1 00:00:00 2036 GMT",
                              "key": "EC prime256v1", "sha256": _FP}}
SAMPLE_PEM = "-----BEGIN CERTIFICATE-----\nDEV PREVIEW — sample, not a real certificate\n-----END CERTIFICATE-----\n"
SAMPLE_KEY = "-----BEGIN PRIVATE KEY-----\nDEV PREVIEW — sample, not a real key\n-----END PRIVATE KEY-----\n"
SAMPLE_INFO = {"subject": "CN=device.home.arpa,OU=IT,O=Fabric", "issuer": "CN=Fabric Intermediate CA,O=Fabric",
               "sans": ["device.home.arpa", "192.168.1.50"], "key": "RSA 2048", "serial": "0x1A2B3C4D5E",
               "not_before": "Sep 28 00:00:00 2026 GMT", "not_after": "Sep 28 00:00:00 2027 GMT", "sha256": _FP,
               "usage": "TLS Web Server Authentication, TLS Web Client Authentication", "is_ca": False}


def sample_result(kind):
    b64 = base64.b64encode(SAMPLE_PEM.encode()).decode()
    r = {"name": "device.home.arpa", "cert": SAMPLE_PEM, "fullchain": SAMPLE_PEM * 3, "der_b64": b64,
         "info": SAMPLE_INFO}
    if kind == "issue":
        r.update(key=SAMPLE_KEY, p12_b64=b64, p12_password=secrets.token_urlsafe(15))
    if kind == "convert":
        r.update(p7b_b64=b64, p12_b64=b64, p12_password=secrets.token_urlsafe(15))
    return r


class DevState:
    """In-memory sample data; nothing leaves this process."""

    def __init__(self):
        self.data = copy.deepcopy(SAMPLE)
        self.lock = threading.Lock()

    def zones(self):
        return [{"key": k, "name": z["name"], "records": len(z["records"]), "reverse": False}
                for k, z in self.data["zones"].items()]

    def reverse(self):
        """The same PTR generation apply uses, over the sample records."""
        if not reverse_zones:
            return {"zones": {}, "skipped": []}
        dns = {}
        for k, z in self.data["zones"].items():
            for t, n, v in z["records"]:
                if t in ("A", "AAAA"):
                    dns.setdefault(k, {}).setdefault(t, []).append({"name": n, "ip": v})
        return reverse_zones({"domain": self.data["zones"]["dynamic_zone_var"]["name"], "dns": dns})

    def zone(self, key):
        z = self.data["zones"][key]
        return {"key": key, "name": z["name"], "status": "dev preview — sample data, not served by BIND",
                "records": [dict({"type": t, "index": i, "name": n, "value": v}, **self._ptr(t, v))
                            for i, (t, n, v) in enumerate(z["records"])]}

    @staticmethod
    def _ptr(rtype, value):
        if rtype not in ("A", "AAAA") or not ptr_for_ip:
            return {}
        zone, label = ptr_for_ip(value)
        return {"ptr": f"{label}.{zone}" if zone else "", "ptr_note": "" if zone else label}

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
                section = query.get("view") if query.get("view") in ("reverse", "tsig") else "forward"
                key = query.get("zone") or next(iter(self.state.data["zones"]))
                zone = self.state.zone(key) if section == "forward" and key in self.state.data["zones"] else None
                return self.send(200, views.bind9(self.ctx, section, self.state.zones(), zone=zone,
                                                  types=RECORD_TYPES, msg=query.get("msg", ""),
                                                  err=query.get("err", ""),
                                                  tsig_keys=self.state.data["tsig"] if section == "tsig" else None,
                                                  reverse=self.state.reverse() if section == "reverse" else None))
            if path == "/stepca":
                view = query.get("view", "ca")
                view = view if view in views.STEPCA_VIEWS else "ca"
                return self.send(200, views.stepca(self.ctx, view, SAMPLE_CA, issued=self.state.data["issued"]))
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
            if path == "/stepca/sign/review":
                review = {"pem": SAMPLE_PEM, "subject": SAMPLE_INFO["subject"], "cn": "device.home.arpa",
                          "sans": SAMPLE_INFO["sans"], "key": "RSA 2048", "ca_requested": False, "problems": [],
                          "text": "DEV PREVIEW — a real install shows the decoded request here."}
                return self.send(200, views.stepca(self.ctx, "sign", SAMPLE_CA, review=review))
            if path == "/stepca/inspect":
                item = {"info": SAMPLE_INFO, "trusted": True,
                        "text": "DEV PREVIEW — a real install shows `openssl x509 -text` here."}
                return self.send(200, views.stepca(self.ctx, "inspect", SAMPLE_CA,
                                                   inspected={"kind": "cert", "items": [item]}))
            if path in ("/stepca/sign", "/stepca/issue", "/stepca/convert"):
                kind = path.rsplit("/", 1)[1]
                self.state.log(f"PKI_{kind.upper()}", "dev preview: sample only, nothing signed")
                return self.send(200, views.pki_result(self.ctx, kind, sample_result(kind)))
            if path == "/bind9/tsig/create" or path.endswith("/rotate"):
                name = form.get("name", "") if path.endswith("create") else path.split("/")[3]
                secret = base64.b64encode(os.urandom(32)).decode()
                ini = (f"# RFC2136 credentials for TSIG key: {name}\ndns_rfc2136_server = 192.168.1.53\n"
                       f"dns_rfc2136_port = 53\ndns_rfc2136_name = {name}\ndns_rfc2136_secret = {secret}\n"
                       f"dns_rfc2136_algorithm = HMAC-SHA256\ndns_rfc2136_base_domain = {form.get('zone') or 'home.arpa'}\n")
                if path.endswith("create") and name:
                    self.state.data["tsig"].append({"name": name, "algorithm": "hmac-sha256", "types": "TXT",
                                                    "scope": f"(dev preview) {form.get('scope', '')}", "acls": []})
                self.state.log("TSIG_ADD" if path.endswith("create") else "TSIG_SECRET", f"key={name} (in memory)")
                return self.send(200, views.tsig_result(self.ctx, name or "preview", secret, ini,
                                                        "created" if path.endswith("create") else "rotated"))
            if path.startswith("/bind9/tsig/") and path.endswith("/delete"):
                name = path.split("/")[3]
                self.state.data["tsig"] = [k for k in self.state.data["tsig"] if k["name"] != name]
                return self.send(303, b"", location="/bind9?view=tsig&msg=" +
                                 urllib.parse.quote(f"TSIG key {name} removed (dev preview: in memory)."))
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
