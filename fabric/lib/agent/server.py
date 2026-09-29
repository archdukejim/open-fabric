#!/usr/bin/env python3
"""fabric-agent: the privileged half of the web UI.

Runs on the host as root (systemd `fabric-agent`) and serves a small JSON API
on a unix socket that is mounted into the unprivileged `webui` container.
It is deliberately not a general executor: every endpoint maps to one
fixed operation in fabriclib (one file per operation), inputs are validated there, and every change
is written to the audit log with the acting user.

Only peers whose uid is listed in --allow-uid (the webui container user) or
root may connect; this is checked with SO_PEERCRED on every connection, on
top of the socket's 0660 root:<webui gid> permissions.

  GET  /v1/version | /v1/services | /v1/zones | /v1/zones/<key> | /v1/audit
  POST /v1/zones/<key>/records          {actor, type, name, ip|target|...}
  POST /v1/zones/<key>/records/delete   {actor, type, index, name}
  POST /v1/apply                        {actor}
  POST /v1/events                       {actor, action, detail}  (login audit)
  GET  /v1/pki/ca | /v1/pki/issued | /v1/tsig | /v1/reverse-zones
  POST /v1/pki/describe-csr             {actor, csr}
  POST /v1/pki/sign                     {actor, csr, days}
  POST /v1/pki/issue                    {actor, cn, sans, key_type, days}
  POST /v1/pki/inspect                  {actor, data}
  POST /v1/pki/convert                  {actor, cert, key}
  POST /v1/tsig                         {actor, name, zone, scope, hosts, types, secret}
  POST /v1/tsig/<name>/rotate | /v1/tsig/<name>/delete   {actor}
  GET  /v1/devices | /v1/people | /v1/vault | /v1/vault/slots | /v1/vault/devices
  POST /v1/vault/slots/<id>/test | /v1/vault/slots/<id>/remove | /v1/vault/rotate   {actor}
  POST /v1/vault/slots/add-usb      {actor, disk, label}
  POST /v1/devices {actor, name, fields} | /v1/devices/<name> {actor, fields} | /v1/devices/<name>/delete
  POST /v1/devices/<name>/certs      {actor, sha256, link}
  POST /v1/roles {actor, name, fields} | /v1/roles/<name> {actor, fields} | /v1/roles/<name>/delete
"""
import argparse
import json
import os
import re
import socket
import socketserver
import struct
import sys
import traceback
import urllib.parse
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from fabriclib.common.errors import ValidationError  # noqa: E402
from fabriclib.common.load_vars import load_vars  # noqa: E402
from fabriclib.common.read_audit import read_audit  # noqa: E402
from fabriclib.common.write_audit import write_audit  # noqa: E402
from fabriclib.dns.add_record import add_record  # noqa: E402
from fabriclib.dns.create_zone_tsig_key import create_zone_tsig_key  # noqa: E402
from fabriclib.dns.constants import RECORD_TYPES  # noqa: E402
from fabriclib.dns.list_tsig_keys import list_tsig_keys  # noqa: E402
from fabriclib.dns.list_zones import list_zones  # noqa: E402
from fabriclib.dns.remove_record import remove_record  # noqa: E402
from fabriclib.dns.remove_tsig_key import remove_tsig_key  # noqa: E402
from fabriclib.dns.reverse_zones import reverse_zones  # noqa: E402
from fabriclib.dns.rotate_tsig_key import rotate_tsig_key  # noqa: E402
from fabriclib.dns.zone_detail import zone_detail  # noqa: E402
from fabriclib.ldap.add_device import add_device  # noqa: E402
from fabriclib.ldap.add_role import add_role  # noqa: E402
from fabriclib.ldap.device_overview import device_overview  # noqa: E402
from fabriclib.ldap.link_device_cert import link_device_cert  # noqa: E402
from fabriclib.ldap.list_people import list_people  # noqa: E402
from fabriclib.ldap.remove_device import remove_device  # noqa: E402
from fabriclib.ldap.remove_role import remove_role  # noqa: E402
from fabriclib.ldap.update_device import update_device  # noqa: E402
from fabriclib.ldap.update_role import update_role  # noqa: E402
from fabriclib.pki.ca_summary import ca_summary  # noqa: E402
from fabriclib.vault.add_usb_slot import add_usb_slot  # noqa: E402
from fabriclib.vault.detect_devices import detect_devices  # noqa: E402
from fabriclib.vault.list_slots import list_slots  # noqa: E402
from fabriclib.vault.remove_slot import remove_slot  # noqa: E402
from fabriclib.vault.rotate_vault_key import rotate_vault_key  # noqa: E402
from fabriclib.vault.run_vault_command import restart_openbao  # noqa: E402
from fabriclib.vault.test_slot import test_slot  # noqa: E402
from fabriclib.vault.vault_status import vault_status  # noqa: E402
from fabriclib.pki.convert_cert import convert_cert  # noqa: E402
from fabriclib.pki.describe_csr import describe_csr  # noqa: E402
from fabriclib.pki.inspect_pem import inspect_pem  # noqa: E402
from fabriclib.pki.issue_key_pair import issue_key_pair  # noqa: E402
from fabriclib.pki.list_issued import list_issued  # noqa: E402
from fabriclib.pki.sign_csr import sign_csr  # noqa: E402
from fabriclib.system.apply_changes import apply_changes  # noqa: E402
from fabriclib.system.service_status import service_status  # noqa: E402
from fabriclib.system.version_info import version_info  # noqa: E402

MAX_BODY = 64 * 1024
ACTOR_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._@-]{0,63}$")
EVENT_ACTIONS = {"LOGIN", "LOGOUT", "LOGIN_DENIED"}


class Handler(BaseHTTPRequestHandler):
    server_version = "fabric-agent"
    sys_version = ""
    allowed_uids = {0}

    def address_string(self):
        return "webui"

    def log_message(self, fmt, *args):
        sys.stderr.write(f"{fmt % args}\n")

    def reply(self, status, obj):
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def peer_ok(self):
        creds = self.connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        _pid, uid, _gid = struct.unpack("3i", creds)
        return uid in self.allowed_uids

    def body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise ValidationError("request too large")
        data = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(data, dict):
            raise ValidationError("expected a JSON object")
        return data

    @staticmethod
    def actor(data):
        actor = str(data.get("actor", ""))
        if not ACTOR_RE.match(actor):
            raise ValidationError("invalid actor")
        return actor

    def do_GET(self):
        self.dispatch("GET")

    def do_POST(self):
        self.dispatch("POST")

    def dispatch(self, method):
        if not self.peer_ok():
            return self.reply(403, {"error": "peer not allowed"})
        try:
            parts = [urllib.parse.unquote(p) for p in urllib.parse.urlsplit(self.path).path.strip("/").split("/")]
            if parts[:1] != ["v1"]:
                return self.reply(404, {"error": "not found"})
            route = parts[1:]
            if method == "GET":
                if route == ["version"]:
                    return self.reply(200, version_info())
                if route == ["services"]:
                    return self.reply(200, service_status())
                if route == ["zones"]:
                    return self.reply(200, list_zones())
                if len(route) == 2 and route[0] == "zones":
                    return self.reply(200, zone_detail(route[1]))
                if route == ["audit"]:
                    return self.reply(200, read_audit())
                if route == ["pki", "ca"]:
                    return self.reply(200, ca_summary(load_vars()))
                if route == ["pki", "issued"]:
                    return self.reply(200, list_issued())
                if route == ["tsig"]:
                    return self.reply(200, list_tsig_keys())
                if route == ["reverse-zones"]:
                    return self.reply(200, reverse_zones(load_vars()))
                if route == ["devices"]:
                    return self.reply(200, device_overview(load_vars()))
                if route == ["people"]:
                    return self.reply(200, list_people(load_vars()))
                if route == ["vault"]:
                    return self.reply(200, vault_status(load_vars()))
                if route == ["vault", "slots"]:
                    v = load_vars()
                    return self.reply(200, {"slots": list_slots(v), "host": v.get("hostname", "")})
                if route == ["vault", "devices"]:
                    return self.reply(200, detect_devices())
                return self.reply(404, {"error": "not found"})

            data = self.body()
            actor = self.actor(data)
            if len(route) == 3 and route[0] == "zones" and route[2] == "records":
                rtype = data.get("type", "")
                if rtype not in RECORD_TYPES:
                    raise ValidationError("unsupported record type")
                return self.reply(200, add_record(actor, route[1], rtype, data, source="web"))
            if len(route) == 4 and route[0] == "zones" and route[2:] == ["records", "delete"]:
                try:
                    index = int(data.get("index", -1))
                except (TypeError, ValueError):
                    raise ValidationError("invalid index")
                return self.reply(200, remove_record(actor, route[1], str(data.get("type", "")),
                                                    index, str(data.get("name", "")), source="web"))
            if route == ["apply"]:
                ok, output = apply_changes(actor, source="web")
                return self.reply(200, {"ok": ok, "output": output})
            if route[:1] == ["pki"] and len(route) == 2:
                return self.reply(200, self.pki(route[1], actor, data))
            if route == ["tsig"]:
                key, secret, ini = create_zone_tsig_key(actor, text(data, "name"), text(data, "zone"),
                                                        text(data, "scope"), strings(data, "hosts"),
                                                        strings(data, "types"), text(data, "secret"), source="web")
                return self.reply(200, {"key": key, "secret": secret, "ini": ini})
            if len(route) == 3 and route[0] == "tsig" and route[2] == "rotate":
                secret, ini = rotate_tsig_key(actor, route[1], source="web")
                return self.reply(200, {"secret": secret, "ini": ini})
            if len(route) == 3 and route[0] == "tsig" and route[2] == "delete":
                remove_tsig_key(actor, route[1], source="web")
                return self.reply(200, {})
            if route[:1] == ["vault"]:
                return self.reply(200, self.vault(route[1:], actor, data))
            if route[:1] in (["devices"], ["roles"]):
                return self.reply(200, self.directory(route, actor, data) or {})
            if route == ["events"]:
                action = data.get("action")
                if action not in EVENT_ACTIONS:
                    raise ValidationError("unsupported event")
                write_audit(actor, action, str(data.get("detail", ""))[:200], source="web")
                return self.reply(200, {})
            return self.reply(404, {"error": "not found"})
        except ValidationError as exc:
            self.reply(400, {"error": str(exc)})
        except (ValueError, json.JSONDecodeError):
            self.reply(400, {"error": "malformed request"})
        except Exception:
            traceback.print_exc()
            self.reply(500, {"error": "internal error"})


    @staticmethod
    def pki(op, actor, data):
        """The manual PKI operations (one fabriclib.pki file each)."""
        if op == "describe-csr":
            return describe_csr(text(data, "csr"))
        if op == "sign":
            return sign_csr(load_vars(), actor, text(data, "csr"), data.get("days"), text(data, "device"))
        if op == "issue":
            return issue_key_pair(load_vars(), actor, text(data, "cn"), strings(data, "sans"),
                                  text(data, "key_type"), data.get("days"), text(data, "device"))
        if op == "inspect":
            return inspect_pem(load_vars(), text(data, "data"))
        if op == "convert":
            return convert_cert(load_vars(), actor, text(data, "cert"), text(data, "key"))
        raise ValidationError("unknown operation")

    @staticmethod
    def vault(route, actor, data):
        """Unlock-method changes (fabriclib.vault)."""
        v = load_vars()
        if route == ["slots", "add-usb"]:
            return {"id": add_usb_slot(v, actor, text(data, "disk"), text(data, "label"))}
        if len(route) == 3 and route[0] == "slots" and route[2] == "test":
            return {"ok": test_slot(v, actor, route[1])}
        if len(route) == 3 and route[0] == "slots" and route[2] == "remove":
            remove_slot(v, actor, route[1])
            return {"ok": True}
        if route == ["rotate"]:
            return rotate_vault_key(v, actor, lambda: restart_openbao(v))
        raise ValidationError("unknown operation")

    @staticmethod
    def directory(route, actor, data):
        """Devices and device roles in 389-DS (fabriclib.ldap, as cn=device_admin)."""
        v = load_vars()
        kind, rest = route[0], route[1:]
        add, update, remove = ((add_device, update_device, remove_device) if kind == "devices"
                               else (add_role, update_role, remove_role))
        if not rest:
            return {"name": add(v, actor, text(data, "name"), fields(data), source="web")}
        if len(rest) == 1:
            return update(v, actor, rest[0], fields(data), source="web")
        if rest[1:] == ["delete"]:
            return remove(v, actor, rest[0], source="web")
        if kind == "devices" and rest[1:] == ["certs"]:
            return link_device_cert(v, actor, rest[0], text(data, "sha256"), bool(data.get("link", True)), source="web")
        raise ValidationError("unknown operation")


def fields(data):
    """A device/role form: text values and lists of text only."""
    value = data.get("fields") or {}
    if not isinstance(value, dict) or len(value) > 20:
        raise ValidationError("fields must be an object")
    for k, x in value.items():
        ok = isinstance(x, (str, bool)) or (isinstance(x, list) and len(x) <= 100 and all(isinstance(i, str) for i in x))
        if not ok:
            raise ValidationError(f"field {k} has an unsupported value")
    return value


def text(data, field):
    value = data.get(field, "")
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be text")
    return value


def strings(data, field):
    value = data.get(field) or []
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value) or len(value) > 100:
        raise ValidationError(f"{field} must be a list of text")
    return value


class UnixServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--socket", required=True)
    ap.add_argument("--socket-gid", type=int, required=True, help="group allowed to connect (webui container gid)")
    ap.add_argument("--allow-uid", type=int, action="append", default=[], help="peer uid allowed besides root")
    args = ap.parse_args()

    Handler.allowed_uids = {0, *args.allow_uid}
    if os.path.exists(args.socket):
        os.unlink(args.socket)
    old_umask = os.umask(0o117)
    try:
        server = UnixServer(args.socket, Handler)
    finally:
        os.umask(old_umask)
    os.chown(args.socket, 0, args.socket_gid)
    os.chmod(args.socket, 0o660)
    print(f"fabric-agent listening on {args.socket} (uids {sorted(Handler.allowed_uids)})", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
