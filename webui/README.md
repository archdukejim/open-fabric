# webui

**Open Fabric** (*web control*): the control-plane web UI. It runs in its own
unprivileged container (`fabric-web`) and holds no power: every action is a
request to `fabric-agent` over a unix socket, checked against the signed-in
person's permissions. Installed by the package as
`/usr/lib/fabricctl/fabric/lib/webui/` and built into `fabric/web:local`
from `/opt/fabric/jinja/webui/build/` (see `installers/deb/`).

| File | What |
|---|---|
| `server.py` | The HTTPS-behind-nginx app: security gates (client certificate, Keycloak sign-in), sessions, CSRF, routes |
| `views.py` | Every page (Jinja templates) and what each tab needs |
| `agentclient.py` | The fabric-agent API client: one function per agent route |
| `oidc.py` | Keycloak OpenID Connect: code flow with PKCE, token verification (also used by `fabric-agent`) |
| `tlsclient.py` | HTTPS client pinned to the fabric root CA (also used by fabricctl's Keycloak code) |
| `devserver.py` | Dev preview: the real pages with sample data, no sign-in, never in production |
| `Dockerfile` | The image: Python and Jinja2 on the pinned Debian base, non-root |
| `.dockerignore` | Keep caches out of the image |
| `__init__.py` | Makes `webui` a package (`from webui import views`) |
