# fabricctl/lib/agent

`fabric-agent` is the root daemon behind the web UI. It runs on the host
(systemd `fabric-agent`) and serves a fixed, permission-checked JSON API over a
unix socket mounted into the unprivileged `fabric-web` container: every route
maps to one fabriclib operation, callers are checked by peer uid and by the
signed-in person's Keycloak token, and every change is audited. It never runs
arbitrary commands.

| File | What |
|---|---|
| `server.py` | The agent: socket server, peer and token checks (`fabriclib/rbac`), routing of each `/v1/...` request to its fabriclib function |
| `__init__.py` | Empty; makes `agent` a package |
| `README.md` | This file |
