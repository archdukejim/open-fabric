#!/usr/bin/env python3
"""fabric-agent: the privileged half of the web UI.

Runs on the host as root (systemd `fabric-agent`) and serves a small JSON API
on a unix socket that is mounted into the unprivileged `webui` container.
It is deliberately not a general executor: every endpoint maps to one
fixed operation in fabriclib (one file per operation), inputs are validated there, and every change
is written to the audit log with the acting user.

Only peers whose uid is listed in --allow-uid (the fabric-web container user)
or root may connect; this is checked with SO_PEERCRED on every connection, on
top of the socket's 0660 root:<webui gid> permissions.

Every call from the web UI carries the signed-in person's Keycloak ID token
(Authorization: Bearer). The agent verifies it itself and allows the call
only if the token grants the permission the route needs
(fabriclib/rbac/required_permission.py; unlisted routes are refused). The
acting user in the audit log is the token's user, never a value from the
request. Root peers (the host itself) are not asked for a token.

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
  POST /v1/vault/slots/add-security-key {actor, module, token, pin, key_id, label}
  POST /v1/vault/slots/add-hsm      {endpoint, key_id, ca, cert, key, server_name, label}
  POST /v1/devices {actor, name, fields} | /v1/devices/<name> {actor, fields} | /v1/devices/<name>/delete
  POST /v1/devices/<name>/certs      {actor, sha256, link}
  POST /v1/roles {actor, name, fields} | /v1/roles/<name> {actor, fields} | /v1/roles/<name>/delete
  POST /v1/people {uid, first, last, email} | /v1/people/<uid>/reset   (one-time password returned)
  GET  /v1/dhcp | POST /v1/dhcp/reservations {mac, ip, hostname} | /v1/dhcp/reservations/<mac>/delete
  GET  /v1/radius | /v1/radius/guides (setup guides, Windows scripts) | POST /v1/radius/clients {name, address, message_authenticator, secret?}
       | /v1/radius/clients/<name>/rotate {secret?} | /v1/radius/clients/<name>/delete   (secret returned once)
       | /v1/radius/people {group, vlan, priority} | /v1/radius/people/<group>/delete
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
from fabriclib.keycloak.create_person import create_person  # noqa: E402
from fabriclib.dhcp.add_reservation import add_reservation  # noqa: E402
from fabriclib.dhcp.dhcp_overview import dhcp_overview  # noqa: E402
from fabriclib.dhcp.remove_reservation import remove_reservation  # noqa: E402
from fabriclib.radius.add_radius_client import add_radius_client  # noqa: E402
from fabriclib.radius.map_radius_group import map_radius_group  # noqa: E402
from fabriclib.radius.radius_guides import radius_guides  # noqa: E402
from fabriclib.radius.radius_overview import radius_overview  # noqa: E402
from fabriclib.radius.remove_radius_client import remove_radius_client  # noqa: E402
from fabriclib.radius.rotate_radius_secret import rotate_radius_secret  # noqa: E402
from fabriclib.radius.unmap_radius_group import unmap_radius_group  # noqa: E402
from fabriclib.keycloak.reset_sign_in import reset_sign_in  # noqa: E402
from fabriclib.keycloak.verify_user_token import verify_user_token  # noqa: E402
from fabriclib.rbac.required_permission import required_permission  # noqa: E402
from fabriclib.rbac.user_permissions import user_permissions  # noqa: E402
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
from fabriclib.vault.add_kmip_slot import add_kmip_slot  # noqa: E402
from fabriclib.vault.add_security_key_slot import add_security_key_slot  # noqa: E402
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
        """Purpose: the client name used in request log lines (a unix socket peer has no address).
        Inputs:  none.
        Returns: str, always "fabric-web".
        Fails:   never.
        Feeds:   BaseHTTPRequestHandler's logging (log_request / log_error)."""
        return "fabric-web"

    def log_message(self, fmt, *args):
        """Purpose: write one request log line to stderr (the systemd journal of fabric-agent).
        Inputs:  fmt — %-format string; args — its values (from BaseHTTPRequestHandler).
        Returns: None.
        Fails:   never in practice (a bad format would raise TypeError from the base class's own calls).
        Feeds:   BaseHTTPRequestHandler (every request and error)."""
        sys.stderr.write(f"{fmt % args}\n")

    def reply(self, status, obj):
        """Purpose: send a complete JSON response.
        Inputs:  status — int HTTP status; obj — any JSON-serialisable object.
        Returns: None; status line, Content-Type application/json, Content-Length and the body are written.
        Fails:   TypeError if obj is not JSON-serialisable (inside dispatch's try it becomes a 500); OSError
                 (BrokenPipeError) if the peer has gone.
        Feeds:   dispatch (every answer)."""
        body = json.dumps(obj).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def peer_uid(self):
        """Purpose: the uid of the process on the other end of the unix socket (SO_PEERCRED; kernel-supplied, cannot be
                 forged by the peer).
        Inputs:  none; reads self.connection.
        Returns: int uid.
        Fails:   OSError if the socket option cannot be read (not a unix socket).
        Feeds:   dispatch (allowed_uids check), authorize (root peers skip the token)."""
        creds = self.connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, struct.calcsize("3i"))
        return struct.unpack("3i", creds)[1]

    def authorize(self, method, route):
        """Purpose: decide whether this request may run: root peers always; everyone else needs a valid Keycloak ID
                 token that grants the permission the route requires.
        Inputs:  method — "GET" or "POST"; route — list of path segments after /v1/. Reads the "Authorization: Bearer
                 <token>" header and vars (load_vars) for token verification.
        Returns: None when allowed, with self.user = the token's preferred_username and self.perms = its permission set
                 (both None for a root peer); otherwise (status, error): (401, reason) when verify_user_token rejects
                 the token or it is missing; (403, "not allowed") when required_permission lists no permission for the
                 route (default deny); (403, "you need the permission <p>") when the token lacks it ("session" needs
                 none).
        Fails:   exceptions other than ValidationError (e.g. KeyError on a token without preferred_username, OSError
                 from load_vars) propagate to dispatch, which answers 500.
        Feeds:   dispatch; self.user feeds actor, self.perms the people-reset privilege check."""
        self.user, self.perms = None, None
        if self.peer_uid() == 0:
            return None
        auth = self.headers.get("Authorization", "")
        try:
            claims = verify_user_token(load_vars(), auth[7:] if auth.startswith("Bearer ") else "")
        except ValidationError as exc:
            return 401, str(exc)
        need = required_permission(method, route)
        if need is None:
            return 403, "not allowed"
        if need != "session" and need not in user_permissions(claims):
            return 403, f"you need the permission {need}"
        self.user, self.perms = claims["preferred_username"], user_permissions(claims)
        return None

    def body(self):
        """Purpose: read and parse the request's JSON body.
        Inputs:  none; reads the Content-Length header and self.rfile. An empty body counts as {}.
        Returns: dict, the parsed object.
        Fails:   ValidationError("request too large") over MAX_BODY (64 KiB), ValidationError("expected a JSON object")
                 for any other JSON value (both -> 400 in dispatch); ValueError / json.JSONDecodeError for a bad
                 Content-Length or invalid JSON (-> 400 "malformed request"). A negative Content-Length is not refused:
                 read(-n) then waits for the peer to close the connection.
        Feeds:   dispatch (every POST)."""
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            raise ValidationError("request too large")
        data = json.loads(self.rfile.read(length) or b"{}")
        if not isinstance(data, dict):
            raise ValidationError("expected a JSON object")
        return data

    def actor(self, data):
        """Purpose: the user name recorded in the audit log for this change.
        Inputs:  data — the request body; its "actor" is used only for root peers (no token).
        Returns: str — the verified token's user when there is one, else data["actor"].
        Fails:   ValidationError("invalid actor") (-> 400) when a root peer's actor is missing or does not match
                 ACTOR_RE (1-64 characters of letters, digits, . _ @ -, starting with a letter or digit).
        Feeds:   dispatch -> every fabriclib change operation and write_audit."""
        if self.user:                       # the verified token's user, not what the request says
            return self.user
        actor = str(data.get("actor", ""))
        if not ACTOR_RE.match(actor):
            raise ValidationError("invalid actor")
        return actor

    def do_GET(self):
        """Purpose: entry point for GET requests (called by BaseHTTPRequestHandler).
        Inputs:  none; the request is in self.path / self.headers.
        Returns: None; the answer is sent by dispatch.
        Fails:   as dispatch (errors become JSON replies).
        Feeds:   dispatch("GET")."""
        self.dispatch("GET")

    def do_POST(self):
        """Purpose: entry point for POST requests (called by BaseHTTPRequestHandler).
        Inputs:  none; the request is in self.path / self.headers / self.rfile.
        Returns: None; the answer is sent by dispatch.
        Fails:   as dispatch (errors become JSON replies).
        Feeds:   dispatch("POST")."""
        self.dispatch("POST")

    def dispatch(self, method):
        """Purpose: route one /v1/ request to exactly one fabriclib operation and reply with its result as JSON.
        Inputs:  method — "GET" or "POST"; self.path (URL-decoded path segments; the query string is ignored), the
                 Authorization header (see authorize) and, for POST, the JSON body (see body; actor from actor()). GET:
                 version, services, zones, zones/<key>, audit, pki/ca, pki/issued, tsig, reverse-zones, devices, people,
                 dhcp, radius, radius/guides, vault, vault/slots, vault/devices. POST: zones/<key>/records[/delete],
                 apply, pki/<op>, tsig, tsig/<name>/rotate|delete, vault/..., devices/..., roles/...,
                 dhcp/reservations[/<mac>/delete], radius/clients[/<name>/rotate|delete],
                 radius/people[/<group>/delete], people, people/<uid>/reset, events.
        Returns: None; replies 200 with the operation's result (DHCP and RADIUS changes run apply_changes and include
                 "applied" and the last 2000 characters of its output; secrets and one-time passwords are returned
                 once).
        Fails:   never raises; replies 403 "peer not allowed" when the peer uid is not in allowed_uids; 404 "not found"
                 for a path outside /v1 or an unknown route; 401/403 from authorize; 400 with the message for
                 ValidationError (bad input, unsupported record type or event, invalid index, fabriclib refusals); 400
                 "malformed request" for ValueError/JSON errors; 500 "internal error" (traceback to stderr) for anything
                 else.
        Feeds:   do_GET, do_POST. Calls fabriclib: dns (list_zones, zone_detail, add_record, remove_record,
                 list_tsig_keys, create_zone_tsig_key, rotate_tsig_key, remove_tsig_key, reverse_zones), system
                 (version_info, service_status, apply_changes), common (read_audit, write_audit), pki (ca_summary,
                 list_issued), ldap (device_overview, list_people), dhcp, radius, vault (vault_status, list_slots,
                 detect_devices), keycloak (create_person, reset_sign_in), plus pki, vault and directory below.
        Notes:   POST apply only needs dns:write (required_permission), though it runs the whole deployment."""
        if self.peer_uid() not in self.allowed_uids:
            return self.reply(403, {"error": "peer not allowed"})
        try:
            parts = [urllib.parse.unquote(p) for p in urllib.parse.urlsplit(self.path).path.strip("/").split("/")]
            if parts[:1] != ["v1"]:
                return self.reply(404, {"error": "not found"})
            route = parts[1:]
            refused = self.authorize(method, route)
            if refused:
                return self.reply(refused[0], {"error": refused[1]})
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
                if route == ["dhcp"]:
                    return self.reply(200, dhcp_overview(load_vars()))
                if route == ["radius"]:
                    return self.reply(200, radius_overview(load_vars()))
                if route == ["radius", "guides"]:
                    return self.reply(200, radius_guides(load_vars()))
                if route == ["vault"]:
                    return self.reply(200, vault_status(load_vars()))
                if route == ["vault", "slots"]:
                    v = load_vars()
                    return self.reply(200, {"slots": list_slots(v), "host": v.get("hostname", "")})
                if route == ["vault", "devices"]:
                    return self.reply(200, detect_devices(v=load_vars()))
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
            if route == ["dhcp", "reservations"]:
                saved = add_reservation(actor, text(data, "mac"), text(data, "ip"), text(data, "hostname"), source="web")
                ok, output = apply_changes(actor, source="web")
                return self.reply(200, {"reservation": saved, "applied": ok, "output": output[-2000:]})
            if len(route) == 4 and route[:2] == ["dhcp", "reservations"] and route[3] == "delete":
                remove_reservation(actor, route[2], source="web")
                ok, output = apply_changes(actor, source="web")
                return self.reply(200, {"applied": ok, "output": output[-2000:]})
            if route == ["radius", "clients"]:
                secret = add_radius_client(actor, text(data, "name"), text(data, "address"),
                                           bool(data.get("message_authenticator", True)),
                                           text(data, "secret") or None, source="web")
                ok, output = apply_changes(actor, source="web")
                return self.reply(200, {"secret": secret, "applied": ok, "output": output[-2000:]})
            if route == ["radius", "people"]:
                saved = map_radius_group(actor, text(data, "group"), text(data, "vlan") or None,
                                         text(data, "priority") or 100, source="web")
                ok, output = apply_changes(actor, source="web")
                return self.reply(200, {"mapping": saved, "applied": ok, "output": output[-2000:]})
            if len(route) == 4 and route[:2] == ["radius", "people"] and route[3] == "delete":
                unmap_radius_group(actor, route[2], source="web")
                ok, output = apply_changes(actor, source="web")
                return self.reply(200, {"applied": ok, "output": output[-2000:]})
            if len(route) == 4 and route[:2] == ["radius", "clients"] and route[3] in ("rotate", "delete"):
                secret = None
                if route[3] == "rotate":
                    secret = rotate_radius_secret(actor, route[2], text(data, "secret") or None, source="web")
                else:
                    remove_radius_client(actor, route[2], source="web")
                ok, output = apply_changes(actor, source="web")
                return self.reply(200, {"secret": secret, "applied": ok, "output": output[-2000:]})
            if route == ["people"]:
                return self.reply(200, {"password": create_person(load_vars(), actor, text(data, "uid"), text(data, "first"),
                                                                  text(data, "last"), text(data, "email"))})
            if len(route) == 3 and route[0] == "people" and route[2] == "reset":
                privileged = self.perms is None or "system:admin" in self.perms     # root, or the admin bundle
                return self.reply(200, {"password": reset_sign_in(load_vars(), actor, route[1], privileged)})
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
        """Purpose: the manual PKI operations of POST /v1/pki/<op> (one fabriclib.pki file each).
        Inputs:  op — "describe-csr" | "sign" | "issue" | "inspect" | "convert"; actor — str; data — body with csr,
                 days, device, cn, sans, key_type, data, cert, key as each operation needs (text fields must be
                 strings).
        Returns: the fabriclib result: describe_csr, sign_csr, issue_key_pair, inspect_pem or convert_cert.
        Fails:   ValidationError("unknown operation") for another op, or from text/strings and the fabriclib function
                 (-> 400); other exceptions -> 500 in dispatch.
        Feeds:   dispatch (POST pki/<op>)."""
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
        """Purpose: changes to OpenBao's unlock methods, POST /v1/vault/... (fabriclib.vault).
        Inputs:  route — segments after "vault": ["slots","add-usb"], ["slots","add-hsm"], ["slots","add-security-key"],
                 ["slots",<id>,"test"], ["slots",<id>,"remove"], ["rotate"]; actor — str; data — body (disk, label,
                 endpoint, key_id, ca, cert, key, server_name, module, token, pin as each needs).
        Returns: {"id": slot id} for an add; {"ok": bool} for test and remove; rotate_vault_key's result for rotate (it
                 restarts OpenBao through restart_openbao).
        Fails:   ValidationError("unknown operation") for another route, or from text() and fabriclib (-> 400); other
                 exceptions -> 500 in dispatch.
        Feeds:   dispatch (POST vault/...)."""
        v = load_vars()
        if route == ["slots", "add-usb"]:
            return {"id": add_usb_slot(v, actor, text(data, "disk"), text(data, "label"))}
        if route == ["slots", "add-hsm"]:
            return {"id": add_kmip_slot(v, actor, text(data, "endpoint"), text(data, "key_id"), text(data, "ca"),
                                        text(data, "cert"), text(data, "key"), text(data, "server_name"),
                                        text(data, "label"))}
        if route == ["slots", "add-security-key"]:
            return {"id": add_security_key_slot(v, actor, text(data, "module"), text(data, "token"), text(data, "pin"),
                                                text(data, "key_id") or "new", text(data, "label"))}
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
        """Purpose: devices and device roles in 389-DS, POST /v1/devices/... and /v1/roles/... (fabriclib.ldap, bound as
                 cn=device_admin).
        Inputs:  route — ["devices"|"roles"] plus [], [<name>], [<name>,"delete"] or (devices only) [<name>,"certs"];
                 actor — str; data — body: name, fields (see fields), sha256, link.
        Returns: {"name": ...} for an add; the result of update_*/remove_* or link_device_cert otherwise (dispatch
                 replies {} when it is None).
        Fails:   ValidationError("unknown operation") for another route, or from fields()/text() and fabriclib (-> 400);
                 other exceptions -> 500 in dispatch.
        Feeds:   dispatch (POST devices/..., roles/...)."""
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
    """Purpose: validate the "fields" form of a device or role request.
    Inputs:  data — the request body; data["fields"] must be an object of at most 20 entries whose values are text,
             booleans, or lists of at most 100 strings. Missing or empty means {}.
    Returns: dict, the fields unchanged.
    Fails:   ValidationError("fields must be an object") or ("field <k> has an unsupported value") (-> 400).
    Feeds:   Handler.directory (add_device, add_role, update_device, update_role)."""
    value = data.get("fields") or {}
    if not isinstance(value, dict) or len(value) > 20:
        raise ValidationError("fields must be an object")
    for k, x in value.items():
        ok = isinstance(x, (str, bool)) or (isinstance(x, list) and len(x) <= 100 and all(isinstance(i, str) for i in x))
        if not ok:
            raise ValidationError(f"field {k} has an unsupported value")
    return value


def text(data, field):
    """Purpose: read one text field from a request body.
    Inputs:  data — the request body; field — str, the key.
    Returns: str, the value; "" when absent.
    Fails:   ValidationError("<field> must be text") when present but not a string (-> 400).
    Feeds:   Handler.dispatch, pki, vault, directory."""
    value = data.get(field, "")
    if not isinstance(value, str):
        raise ValidationError(f"{field} must be text")
    return value


def strings(data, field):
    """Purpose: read one list-of-text field from a request body.
    Inputs:  data — the request body; field — str, the key.
    Returns: list of str (at most 100); [] when absent or empty.
    Fails:   ValidationError("<field> must be a list of text") for anything else (-> 400).
    Feeds:   Handler.dispatch (tsig hosts/types), Handler.pki (sans)."""
    value = data.get(field) or []
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value) or len(value) > 100:
        raise ValidationError(f"{field} must be a list of text")
    return value


class UnixServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def main():
    """Purpose: start fabric-agent: listen on the unix socket and serve requests, one thread each, until stopped.
    Inputs:  command-line --socket (path, required; an existing file there is removed), --socket-gid (int, required: the
             webui container's group), --allow-uid (int, repeatable: peer uids allowed besides root). Set by
             systemd/fabric-agent.service.j2 (socket <base>/webui/agent/agent.sock).
    Returns: never returns normally (serve_forever).
    Fails:   argparse exits 2 on missing/invalid arguments; OSError if the socket cannot be created, chowned or chmodded
             (must run as root).
    Feeds:   the fabric-agent systemd unit; webui/agentclient.py is its client.
    Notes:   the socket is created under umask 0117, then set to root:<socket-gid> 0660."""
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
