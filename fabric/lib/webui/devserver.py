#!/usr/bin/env python3
"""Fabric web UI — DEV PREVIEW. The real pages (views.py) with sample data:
no sign-in, no client certificate, no fabric-agent, nothing saved or
applied. Record edits live in memory until the process stops.

A separate entry point on purpose: the production server (server.py) has no
dev switch, so this can never be turned on in a real install.

  python3 fabric/lib/webui/devserver.py                      # http://127.0.0.1:8080
  docker run --rm -p 127.0.0.1:8080:8080 --entrypoint /usr/bin/python3 \\
      fabric/web:local /app/webui/devserver.py --bind 0.0.0.0   # from the image
"""
import argparse
import email.parser
import email.policy
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
try:        # the real rules when run from a checkout; the webui image carries only webui/
    from fabriclib.common.errors import ValidationError  # noqa: E402
    from fabriclib.dns.ptr_for_ip import ptr_for_ip  # noqa: E402
    from fabriclib.dns.reverse_zones import reverse_zones  # noqa: E402
    from fabriclib.ldap.common.check_device_fields import check_device_fields  # noqa: E402
    from fabriclib.ldap.common.check_role_fields import check_role_fields  # noqa: E402
    from fabriclib.ldap.constants import DEVICE_NAME_RE, DEVICE_TYPES, PERMISSIONS, ROLE_NAME_RE  # noqa: E402
    from fabriclib.ldap.list_devices import list_devices  # noqa: E402
    from fabriclib.rbac.permissions import BUNDLES, PERMISSIONS as FABRIC_PERMISSIONS  # noqa: E402
except ImportError:
    ptr_for_ip = reverse_zones = list_devices = None
    BUNDLES, FABRIC_PERMISSIONS = {}, {p: "" for p in views.PREVIEW_PERMS}

RECORD_TYPES = ["A", "AAAA", "CNAME", "MX", "TXT", "SRV"]
SAMPLE_DHCP = {"enabled": True, "interfaces": ["eth0"], "lease_time": 86400, "ddns_zone": "dhcp.home.arpa",
               "subnets": [{"subnet": "192.168.1.0/24", "pools": ["192.168.1.100 - 192.168.1.199"],
                            "routers": "192.168.1.1",
                            "reservations": [{"mac": "aa:bb:cc:00:11:22", "ip": "192.168.1.20", "hostname": "printer"}]}],
               "leases": [{"ip": "192.168.1.101", "mac": "02:11:22:33:44:55", "hostname": "laptop1.dhcp.home.arpa",
                           "expires": "2026-09-30T08:00", "state": "active", "subnet_id": 1}],
               "leases_error": ""}
SAMPLE = {
    "services": [("nginx", "active", "healthy"), ("bind9", "active", "healthy"), ("stepca", "active", "healthy"),
                 ("ldap", "active", "healthy"), ("postgres", "active", "healthy"), ("keycloak", "active", "healthy"),
                 ("openbao", "active", "healthy"), ("fabric-web", "active", "healthy"), ("fabric-agent", "active", "")],
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
    "directory": {
        "roles": [{"name": "trusted", "description": "Managed laptops and phones", "priority": 10, "vlan": 10,
                   "permissions": ["dns:dhcp-register", "network:eap-tls", "pki:acme"], "members": ["jims-laptop", "jims-phone"]},
                  {"name": "iot", "description": "Cameras, plugs, thermostats", "priority": 50, "vlan": 30,
                   "permissions": ["dns:dhcp-register", "network:mab"], "members": ["cam-front", "thermostat"]},
                  {"name": "printers", "description": "", "priority": 60, "vlan": None,
                   "permissions": ["network:mab", "pki:scep"], "members": ["printer"]},
                  {"name": "quarantine", "description": "No access; parked devices", "priority": 1, "vlan": 99,
                   "permissions": [], "members": []}],
        "devices": [{"name": "jims-laptop", "type": "laptop", "enabled": True, "macs": ["3c:22:fb:10:20:30"],
                     "owner": "uid=jim,ou=users", "description": "ThinkPad", "certs": [":".join(["AB"] * 32)]},
                    {"name": "jims-phone", "type": "phone", "enabled": True, "macs": ["f2:11:22:33:44:55"],
                     "owner": "uid=jim,ou=users", "description": "", "certs": []},
                    {"name": "cam-front", "type": "camera", "enabled": True, "macs": ["b0:a7:32:00:00:11"],
                     "owner": "", "description": "Front door", "certs": []},
                    {"name": "thermostat", "type": "iot", "enabled": False, "macs": ["18:b4:30:aa:bb:cc"],
                     "owner": "", "description": "Disabled: firmware out of date", "certs": []},
                    {"name": "printer", "type": "printer", "enabled": True, "macs": ["00:1b:a9:12:34:56"],
                     "owner": "", "description": "Office laser", "certs": []}]},
    "people": {"users": [{"uid": "jim", "name": "Jim", "mail": "jim@home.arpa", "locked": False, "groups": ["admins", "users"]},
                         {"uid": "sam", "name": "Sam", "mail": "sam@home.arpa", "locked": False, "groups": ["users"]}],
               "groups": [{"name": "admins", "members": 1}, {"name": "users", "members": 2}],
               "keycloak_url": "https://sso.home.arpa/admin/home.arpa/console/"},
    "issued": [{"when": "2026-09-20T10:12:00", "actor": "dev", "kind": "csr", "subject": "CN=switch-core.home.arpa",
                "sans": ["switch-core.home.arpa", "192.168.1.2"], "not_after": "Sep 20 10:12:00 2027 GMT",
                "status": "valid"},
               {"when": "2025-10-01T08:00:00", "actor": "dev", "kind": "keypair", "subject": "CN=printer.home.arpa",
                "sans": ["printer.home.arpa"], "not_after": "Oct 15 08:00:00 2026 GMT", "status": "expires soon"}],
}
_FP = ":".join(["AB", "12", "CD", "34"] * 8)
SAMPLE_VAULT = {"url": "https://vault.home.arpa/", "reachable": True, "initialized": True, "sealed": False,
                "version": "2.7.0", "seal_type": "static", "storage": "raft", "recovery_seal": True,
                "key": {"path": "/etc/fabric/openbao/unseal.key", "present": True, "ok": True,
                        "detail": "32 bytes, 0400, openbao only"},
                "mounts": [{"path": "apps/", "type": "kv", "version": "2", "description": "secrets for your applications"},
                           {"path": "cubbyhole/", "type": "cubbyhole", "version": None, "description": "per-token private secret storage"},
                           {"path": "fabric/", "type": "kv", "version": "2", "description": "fabric's own secrets"},
                           {"path": "identity/", "type": "identity", "version": None, "description": "identity store"},
                           {"path": "sys/", "type": "system", "version": None, "description": "system endpoints"}],
                "auth": ["approle/", "oidc/", "token/"], "secrets": {"version": 7, "updated": "2026-09-29T09:12:44"}}
SAMPLE_SLOTS = [
    {"id": "local", "type": "local", "label": "Key file on this host", "device": "/etc/fabric/openbao/unseal.key",
     "present": True, "key_id": "fabric-1", "added": "2026-09-28",
     "detail": "always present: while this slot exists, removing a device cannot seal the vault"},
    {"id": "s-yk1", "type": "security-key", "label": "Pi key", "device": "YubiKey 5 Nano · serial 23456781 · key 03",
     "present": True, "key_id": "fabric-1", "added": "2026-09-29", "detail": "the key cannot be copied; its PIN is kept root-only on this host"}]
SAMPLE_DEVICES = {"tokens": [{"vendor": "Yubico", "product": "YubiKey OTP+FIDO+CCID", "serial": "23456781",
                              "usb_id": "1050:0407", "port": "1-1.2"},
                             {"vendor": "Yubico", "product": "YubiKey OTP+FIDO+CCID", "serial": "23456799",
                              "usb_id": "1050:0407", "port": "1-1.3"}],
                  "disks": [{"path": "/dev/sda", "model": "SanDisk Ultra Fit", "serial": "4C530001230912104582",
                             "size_gb": 32.0, "uuids": ["9A1C-33F0"], "labels": ["USB"]}],
                  "pkcs11": [{"module": "/usr/lib/aarch64-linux-gnu/libykcs11.so.2", "library": "libykcs11.so.2",
                              "serial": "23456781", "label": "YubiKey PIV #23456781", "manufacturer": "Yubico (www.yubico.com)",
                              "model": "YubiKey YK5", "pin_state": "ok"},
                             {"module": "/usr/lib/aarch64-linux-gnu/libykcs11.so.2", "library": "libykcs11.so.2",
                              "serial": "23456799", "label": "YubiKey PIV #23456799", "manufacturer": "Yubico (www.yubico.com)",
                              "model": "YubiKey YK5", "pin_state": "ok"}]}
SAMPLE_CA = {"domain": "home.arpa", "certs_url": "http://certs.home.arpa/", "max_days": 1825,
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
        self.data["slots"] = copy.deepcopy(SAMPLE_SLOTS)
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

    def overview(self):
        if not list_devices:
            return None
        d = self.data["directory"]
        return {"devices": list_devices({}, d), "roles": sorted(d["roles"], key=lambda r: (r["priority"], r["name"])),
                "types": DEVICE_TYPES, "permissions": {k: list(v) for k, v in PERMISSIONS.items()}}

    def save(self, kind, name, form):
        """Device/role create or edit, validated by the real fabriclib rules, in memory."""
        d = self.data["directory"]
        if kind == "devices":
            f = check_device_fields({"type": form.get("type"), "owner": form.get("owner"),
                                     "description": form.get("description"), "enabled": bool(form.get("enabled")),
                                     "macs": [m for m in form.get("macs", "").replace(",", " ").split() if m],
                                     "roles": [k[5:] for k in form if k.startswith("role_")]}, d, name)
            entry = next((x for x in d["devices"] if x["name"] == name), None)
            if entry is None:
                if not DEVICE_NAME_RE.match(name) or name == "_new":
                    raise ValidationError("device name: a host name label — lowercase letters, digits and '-'")
                entry = {"name": name, "certs": []}
                d["devices"].append(entry)
            entry.update(type=f["type"], enabled=f["enabled"], macs=f["macs"], description=f["description"],
                         owner=f"uid={f['owner']},ou=users" if f["owner"] else "")
            for r in d["roles"]:
                r["members"] = [m for m in r["members"] if m != name] + ([name] if r["name"] in f["roles"] else [])
        else:
            f = check_role_fields({"description": form.get("description"), "vlan": form.get("vlan"),
                                   "priority": form.get("priority"),
                                   "permissions": [k[5:] for k in form if k.startswith("perm_")]})
            entry = next((x for x in d["roles"] if x["name"] == name), None)
            if entry is None:
                if not ROLE_NAME_RE.match(name):
                    raise ValidationError("role name: lowercase letters, digits, '-' and '_'")
                entry = {"name": name, "members": []}
                d["roles"].append(entry)
            entry.update(f)
        self.log("DEVICE_SAVE" if kind == "devices" else "ROLE_SAVE", f"{name} (in memory)")

    def vault_action(self, parts, form):
        """Unlock-method flows in memory: {"msg": ...} or {"err": ...}."""
        slots = self.data["slots"]
        if form.get("confirm", "") != "pi-core":
            return {"err": "Type this host's name (pi-core) to confirm."}
        if parts[:1] == ["rotate"]:
            n = max(int(sl["key_id"].split("-")[-1]) for sl in slots) + 1
            kept = [sl for sl in slots if sl["present"]]
            for sl in kept:
                sl["key_id"] = f"fabric-{n}"
            dropped = len(slots) - len(kept)
            self.data["slots"] = kept
            self.log("VAULT_ROTATE", f"new key fabric-{n} (dev preview)")
            return {"msg": f"Vault key rotated to fabric-{n}." + (f" {dropped} method(s) without their device removed."
                                                                  if dropped else "")}
        if parts[:1] == ["slots"] and len(parts) == 3:        # /openbao/slots/<id>/<test|remove>
            parts = parts[1:]
        if len(parts) == 2 and parts[1] == "remove":
            if len(slots) < 2:
                return {"err": "The last unlock method cannot be removed."}
            self.data["slots"] = [sl for sl in slots if sl["id"] != parts[0]]
            self.log("VAULT_SLOT_REMOVE", f"{parts[0]} (dev preview)")
            return {"msg": "Unlock method removed (dev preview: nothing changed)."}
        if len(parts) == 2 and parts[1] == "test":
            return {"msg": "Test passed: the method unwrapped the vault key (dev preview)."}
        kind = {"add-security-key": "security-key", "add-usb": "usb", "add-hsm": "hsm"}.get(parts[-1])
        if not kind:
            return {"err": "Unknown action."}
        device = {"security-key": f"YubiKey YK5 · serial {form.get('token', '').rpartition('|')[2]} · key 03",
                  "usb": f"SanDisk Ultra Fit · {form.get('disk', '')} · UUID 9A1C-33F0",
                  "hsm": f"{form.get('endpoint', 'kms')} · key {form.get('key_id', '')}"}[kind]
        slots.append({"id": f"s-{secrets.token_hex(3)}", "type": kind, "label": form.get("label") or kind,
                      "device": device, "present": True, "key_id": slots[0]["key_id"] if slots else "fabric-1",
                      "added": "today", "detail": "dev preview: nothing was written"})
        self.log("VAULT_SLOT_ADD", f"{kind} (dev preview)")
        return {"msg": f"{views.SLOT_TYPES[kind][0]} added and tested (dev preview: nothing was written)."}

    def log(self, action, detail):
        self.data["audit"].insert(0, f"[dev] User: dev (web) | Action: {action} | {detail}\n")


class Handler(BaseHTTPRequestHandler):
    state = DevState()
    ctx = {"user": "dev (preview)", "csrf": "dev", "dev": True, "perms": sorted(FABRIC_PERMISSIONS),
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
                ov = self.state.overview()
                return self.send(200, views.stepca(self.ctx, view, SAMPLE_CA, issued=self.state.data["issued"],
                                                   devices=ov["devices"] if ov else [], device=query.get("device", "")))
            if path == "/openbao":
                view = query.get("view") if query.get("view") in views.OPENBAO_VIEWS else "status"
                return self.send(200, views.openbao(self.ctx, SAMPLE_VAULT, view, self.state.data["slots"],
                                                    SAMPLE_DEVICES, slot_id=query.get("slot", ""), host="pi-core",
                                                    live=True, msg=query.get("msg", ""), err=query.get("err", ""),
                                                    add_live={"security-key": True, "usb": True, "hsm": True}))
            if path == "/dirsrv":
                view = query.get("view") if query.get("view") in ("device", "roles", "role", "people") else "devices"
                kw = {"msg": query.get("msg", ""), "err": query.get("err", "")}
                if view == "people":
                    return self.send(200, views.dirsrv(self.ctx, view, people=self.state.data["people"], **kw))
                data = self.state.overview()
                if data is None:
                    return self.send(200, views.dirsrv(self.ctx, view, unavailable="dev preview from the image "
                                                       "has no fabriclib; run it from a checkout", **kw))
                if view == "device":
                    kw["device"] = next((d for d in data["devices"] if d["name"] == query.get("name")), None)
                    view = view if kw["device"] else "devices"
                if view == "role":
                    kw["role"] = next((r for r in data["roles"] if r["name"] == query.get("name")), None)
                    view = view if kw["role"] else "roles"
                return self.send(200, views.dirsrv(self.ctx, view, data=data, **kw))
            if path == "/kea":
                return self.send(200, views.kea(self.ctx, SAMPLE_DHCP, query.get("msg", ""), query.get("err", "")))
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
        body = self.rfile.read(length)
        ctype = self.headers.get("Content-Type", "")
        if ctype.startswith("multipart/form-data"):          # file inputs (HSM, CSR uploads): text fields only
            msg = email.parser.BytesParser(policy=email.policy.HTTP).parsebytes(
                f"Content-Type: {ctype}\r\n\r\n".encode() + body)
            form = {part.get_param("name", header="content-disposition"):
                    (part.get_payload(decode=True) or b"").decode(errors="replace")
                    for part in (msg.iter_parts() if msg.is_multipart() else []) if part.get_filename() is None}
        else:
            form = dict(urllib.parse.parse_qsl(body.decode(errors="replace")))
        with self.state.lock:
            if path == "/logout":
                return self.send(303, b"", location="/")
            if path == "/apply":
                self.state.log("APPLY", "dev preview: nothing applied")
                return self.send(200, views.apply_result(self.ctx, True,
                                                         "DEV PREVIEW — nothing was rendered or reloaded.\n"
                                                         "On a real install this runs `fabricctl --apply`."))
            if path.startswith("/openbao/"):
                return self.send(303, b"", location="/openbao?" + urllib.parse.urlencode(
                    {"view": "unlock", **self.state.vault_action(path.split("/")[2:], form)}))
            if path.startswith("/kea/reservations"):
                rs = SAMPLE_DHCP["subnets"][0]["reservations"]
                parts = path.split("/")[3:]
                if not parts:
                    rs.append({"mac": form.get("mac", "").lower(), "ip": form.get("ip", ""),
                               "hostname": form.get("hostname", "")})
                    msg = f"Reserved {form.get('ip', '')} (dev preview: nothing applied)."
                else:
                    rs[:] = [r for r in rs if r["mac"] != urllib.parse.unquote(parts[0])]
                    msg = "Reservation removed (dev preview)."
                return self.send(303, b"", location="/kea?" + urllib.parse.urlencode({"msg": msg}))
            if path.startswith("/dirsrv/people/"):
                name, op = (path.split("/")[3:] + ["", ""])[:2]
                users = self.state.data["people"]["users"]
                if name == "_new":
                    uid = form.get("uid", "")
                    if not uid or any(u["uid"] == uid for u in users):
                        return self.send(303, b"", location="/dirsrv?view=people&err=" + urllib.parse.quote(
                            f"{uid or 'a user name'} is missing or already exists"))
                    users.append({"uid": uid, "name": f"{form.get('first', '')} {form.get('last', '')}".strip(),
                                  "mail": form.get("email", ""), "locked": False, "groups": ["users"]})
                    self.state.log("PERSON_CREATE", f"user={uid} (dev preview)")
                    return self.send(200, views.person_result(self.ctx, uid, "created", "dev-preview-not-real"))
                target = next((u for u in users if u["uid"] == name), None)
                if op != "reset" or not target:
                    return self.send(404, views.error_page(404, "Not found."))
                if set(target["groups"]) - {"users"} and "system:admin" not in self.ctx["perms"]:
                    return self.send(303, b"", location="/dirsrv?view=people&err=" + urllib.parse.quote(
                        f"{name} is in a fabric group: only an admin can reset their sign-in"))
                self.state.log("PERSON_RESET", f"user={name} (dev preview)")
                return self.send(200, views.person_result(self.ctx, name, "reset", "dev-preview-not-real"))
            if path.startswith("/dirsrv/") and list_devices:
                kind, name, op = (path.split("/")[2:] + ["", "", ""])[:3]
                d = self.state.data["directory"]
                try:
                    if name == "_new":
                        name = form.get("name", "").strip().lower()
                        if any(x["name"] == name for x in d[kind]):
                            raise ValidationError(f"{name} already exists")
                        self.state.save(kind, name, form)
                        back, msg = {"view": kind[:-1], "name": name}, f"{name} created (in memory)."
                    elif op == "delete":
                        if kind == "roles" and any(r["members"] for r in d["roles"] if r["name"] == name):
                            raise ValidationError(f"role {name} still has devices; take them out first")
                        d[kind] = [x for x in d[kind] if x["name"] != name]
                        for r in d["roles"]:
                            r["members"] = [m for m in r["members"] if m != name]
                        back, msg = {"view": kind}, f"{name} deleted (in memory)."
                    elif op == "certs":
                        for x in d["devices"]:
                            if x["name"] == name:
                                x["certs"] = [c for c in x["certs"] if c != form.get("sha256")]
                        back, msg = {"view": "device", "name": name}, "Certificate unlinked (in memory)."
                    else:
                        self.state.save(kind, name, form)
                        back, msg = {"view": kind[:-1], "name": name}, "Saved (in memory)."
                    return self.send(303, b"", location="/dirsrv?" + urllib.parse.urlencode({**back, "msg": msg}))
                except ValidationError as exc:
                    back = {"view": kind} if name == "_new" or op == "delete" else {"view": kind[:-1], "name": name}
                    return self.send(303, b"", location="/dirsrv?" + urllib.parse.urlencode({**back, "err": str(exc)}))
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
    ap.add_argument("--as", dest="bundle", default="admin",
                    help="see the UI as this role bundle: " + ", ".join(sorted(BUNDLES)) + " (default admin)")
    args = ap.parse_args()
    if args.bundle != "admin":
        if args.bundle not in BUNDLES:
            ap.error(f"unknown bundle {args.bundle!r}")
        Handler.ctx = dict(Handler.ctx, perms=sorted(BUNDLES[args.bundle]),
                           user=f"dev (preview as {args.bundle})")
    server = ThreadingHTTPServer((args.bind, args.port), Handler)
    print(f"Fabric web UI DEV PREVIEW on http://{args.bind}:{args.port}/ — sample data, no sign-in, "
          "nothing is saved. Never expose this.", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
