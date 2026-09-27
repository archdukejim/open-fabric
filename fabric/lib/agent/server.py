#!/usr/bin/env python3
"""fabric-agent: the privileged half of the web UI.

Runs on the host as root (systemd `fabric-agent`) and serves a small JSON API
on a unix socket that is mounted into the unprivileged `webui` container.
It is deliberately not a general executor: every endpoint maps to one
fixed operation in actions.py, inputs are validated there, and every change
is written to the audit log with the acting user.

Only peers whose uid is listed in --allow-uid (the webui container user) or
root may connect; this is checked with SO_PEERCRED on every connection, on
top of the socket's 0660 root:<webui gid> permissions.

  GET  /v1/version | /v1/services | /v1/zones | /v1/zones/<key> | /v1/audit
  POST /v1/zones/<key>/records          {actor, type, name, ip|target|...}
  POST /v1/zones/<key>/records/delete   {actor, type, index, name}
  POST /v1/apply                        {actor}
  POST /v1/events                       {actor, action, detail}  (login audit)
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
from agent import actions  # noqa: E402

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
            raise actions.ValidationError("request too large")
        data = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(data, dict):
            raise actions.ValidationError("expected a JSON object")
        return data

    @staticmethod
    def actor(data):
        actor = str(data.get("actor", ""))
        if not ACTOR_RE.match(actor):
            raise actions.ValidationError("invalid actor")
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
                    return self.reply(200, actions.version_info())
                if route == ["services"]:
                    return self.reply(200, actions.service_status())
                if route == ["zones"]:
                    return self.reply(200, actions.list_zones())
                if len(route) == 2 and route[0] == "zones":
                    return self.reply(200, actions.zone_detail(route[1]))
                if route == ["audit"]:
                    return self.reply(200, actions.read_audit())
                return self.reply(404, {"error": "not found"})

            data = self.body()
            actor = self.actor(data)
            if len(route) == 3 and route[0] == "zones" and route[2] == "records":
                rtype = data.get("type", "")
                if rtype not in actions.RECORD_TYPES:
                    raise actions.ValidationError("unsupported record type")
                return self.reply(200, actions.add_record(actor, route[1], rtype, data))
            if len(route) == 4 and route[0] == "zones" and route[2:] == ["records", "delete"]:
                try:
                    index = int(data.get("index", -1))
                except (TypeError, ValueError):
                    raise actions.ValidationError("invalid index")
                return self.reply(200, actions.delete_record(actor, route[1], str(data.get("type", "")),
                                                             index, str(data.get("name", ""))))
            if route == ["apply"]:
                ok, output = actions.apply_changes(actor)
                return self.reply(200, {"ok": ok, "output": output})
            if route == ["events"]:
                action = data.get("action")
                if action not in EVENT_ACTIONS:
                    raise actions.ValidationError("unsupported event")
                actions.audit(actor, action, str(data.get("detail", ""))[:200])
                return self.reply(200, {})
            return self.reply(404, {"error": "not found"})
        except actions.ValidationError as exc:
            self.reply(400, {"error": str(exc)})
        except (ValueError, json.JSONDecodeError):
            self.reply(400, {"error": "malformed request"})
        except Exception:
            traceback.print_exc()
            self.reply(500, {"error": "internal error"})


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
