# webui

**Open Fabric** (*web control*): the control-plane web UI. It runs in its own
unprivileged container (`fabric-web`) and holds no power: every action is a
request to `fabric-agent` over a unix socket, carrying the signed-in person's
ID token, and `fabric-agent` checks it against their permissions. Installed by
the package as `/usr/lib/fabricctl/fabric/lib/webui/` (the Dockerfile and
`.dockerignore` go to `fabric/jinja/webui/build/`; see `installers/deb/`).
Setup copies that build folder plus this app (as `app/`) into
`<deploy_base_dir>/webui/build/` and builds `fabric/web:local` from it.

| File | What |
|---|---|
| `server.py` | The production app behind nginx on a unix socket: security gates (client certificate from the Step-CA intermediate, Keycloak sign-in bound to it, fabric roles), in-memory sessions, CSRF and Origin checks, vault step-up, and every GET/POST route |
| `views.py` | Every page (Jinja2 templates, autoescaped, no inline script or style) and the stylesheet; hides tabs, menus and forms the person has no permission for |
| `agentclient.py` | The fabric-agent API client: one function per agent route, JSON over the agent's unix socket, the person's ID token per thread |
| `oidc.py` | Keycloak OpenID Connect: authorization code flow with PKCE, token refresh, logout URL, ID token verification (RS256 against the realm JWKS; also used by `fabric-agent`) |
| `tlsclient.py` | HTTPS client that reaches a service by container IP but verifies its certificate for the public hostname against the fabric root CA only (also used by fabricctl's Keycloak code) |
| `devserver.py` | Dev preview: the real pages with sample data, no sign-in, nothing saved; a separate entry point, never in production |
| `Dockerfile` | The image: Python 3, Jinja2, openssl and tini on the digest-pinned Debian base given by the compose file; runs `server.py` as the non-root `webui` user |
| `.dockerignore` | Keeps `__pycache__` and `*.pyc` out of the image |
| `__init__.py` | Empty; makes `webui` a package (`from webui import views`) |
