#!/usr/bin/env python3
"""One fabric install's federation side, for tests/federation/nested.py: the code is imported from the install
tree given first (its own config: vars, secrets, federation registry), so several installs can run side by side.

    role.py <tree> invite <site> <nest>          -> prints {"invitation": ...} (create_invitation)
    role.py <tree> capacity                      -> prints signing_capacity
    role.py <tree> serve <https> <http> <crt> <key> <www>
                                                 -> the federation endpoint over TLS + the certs page, until killed
"""
import http.server
import json
import socketserver
import ssl
import sys
import threading

TREE = sys.argv[1]
sys.path[0:0] = [f"{TREE}/fabric/lib", f"{TREE}/fabric/lib/federation"]
from fabriclib.common.errors import ValidationError  # noqa: E402
from fabriclib.common.load_vars import load_vars  # noqa: E402
from fabriclib.federation.common.signing_capacity import signing_capacity  # noqa: E402
from fabriclib.federation.create_invitation import create_invitation  # noqa: E402

action = sys.argv[2]
if action == "invite":
    try:
        print(json.dumps(create_invitation(load_vars(), "tester", sys.argv[3], nest=int(sys.argv[4]))))
    except ValidationError as e:
        print(json.dumps({"error": str(e)}))
elif action == "capacity":
    print(json.dumps(signing_capacity(load_vars())))
elif action == "serve":
    import server as fed_server  # noqa: E402

    https, port_http, crt, key, www = int(sys.argv[3]), int(sys.argv[4]), sys.argv[5], sys.argv[6], sys.argv[7]

    class TLSServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
        daemon_threads = True
        allow_reuse_address = True

        def get_request(self):
            sock, addr = super().get_request()
            return ctx.wrap_socket(sock, server_side=True), addr

    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ctx.load_cert_chain(crt, key)
    web = socketserver.TCPServer(("127.0.0.1", port_http),
                                 lambda *a: http.server.SimpleHTTPRequestHandler(*a, directory=www))
    threading.Thread(target=web.serve_forever, daemon=True).start()
    tls = TLSServer(("127.0.0.1", https), fed_server.Handler)
    print("ready", flush=True)
    tls.serve_forever()
