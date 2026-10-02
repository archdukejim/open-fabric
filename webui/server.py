#!/usr/bin/env python3
"""webui: browser front end for fabricctl.

Runs unprivileged in its own container (read-only, no capabilities, no
Docker socket). It holds no power of its own: every read and change goes
through fabric-agent on the host (agentclient/), which exposes a fixed,
validated set of operations and audits each one. This file starts the server;
the gates are handler.py, security/ and session/, the pages and actions routes/.

Security model (every request must pass all of these):
  1. nginx requires a client certificate issued by the core Step-CA
     intermediate (ssl_verify_client on, depth 2) and forwards the verified
     subject/issuer/fingerprint. This server listens only on a unix socket
     that nobody but nginx can reach, so those headers cannot be forged.
  2. The issuer must be the Step-CA intermediate itself (sub-CAs rejected).
  3. The user logs in through Keycloak (OIDC code flow + PKCE). The
     Keycloak username must equal the client certificate CN and the user
     must hold the admin realm role.
  4. The session is bound to the certificate fingerprint; presenting the
     cookie with any other certificate ends the session.
  5. State-changing requests are POST-only with a per-session CSRF token
     and a same-origin Origin header.
"""
import argparse
import grp
import json
import os
import socketserver
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from webui import agentclient as actions  # noqa: E402  (fabric-agent API)
from webui.app_state import App  # noqa: E402
from webui.handler import Handler  # noqa: E402


class UnixServer(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
    daemon_threads = True


def main():
    """Purpose: Start the web UI: load the config, point agentclient at fabric-agent, and serve HTTP on a unix socket
             that only nginx's group can use.
    Inputs:  command line --config <path to webui.json> (required); the config's agent_socket, socket, socket_gid
             (int or group name) and the keys App needs.
    Returns: never returns while serving (serve_forever).
    Fails:   SystemExit from argparse without --config; OSError / json.JSONDecodeError reading the config; KeyError
             for a missing key (also from grp.getgrnam for an unknown group); errors from App; OSError binding the
             socket.
    Feeds:   — (the container's ENTRYPOINT in webui/Dockerfile).
    Notes:   A stale socket is removed first; it is created under umask 0117, then group-owned by nginx's group and
             set to 0660, so only nginx can connect and the forwarded certificate headers cannot be forged.
    """
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    args = ap.parse_args()
    with open(args.config) as f:
        cfg = json.load(f)

    actions.configure(cfg["agent_socket"])
    Handler.app = App(cfg)
    sock = cfg["socket"]
    if os.path.exists(sock):
        os.unlink(sock)
    old_umask = os.umask(0o117)
    try:
        server = UnixServer(sock, Handler)
    finally:
        os.umask(old_umask)
    # Group-owned by nginx (this container's user is a member via group_add).
    gid = cfg["socket_gid"]
    os.chown(sock, -1, gid if isinstance(gid, int) else grp.getgrnam(gid).gr_gid)
    os.chmod(sock, 0o660)
    print(f"webui listening on {sock}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
