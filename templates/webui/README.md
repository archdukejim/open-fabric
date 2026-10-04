# jinja/webui

Deploying the web UI container (only with `install_webui`). Rendered by
`deploy.py` into `/opt/webui/`; the `fabric-web` systemd unit runs it after
`fabric-agent`. The image `fabric/web:local` is built from `build/`, which is
not in this folder in the repository: `packaging/deb/assemble-tree.sh` puts
the repository's `packaging/images/webui/Dockerfile` and `.dockerignore` here as `build/`, and
`deploy.py` adds the app code (`lib/webui` → `/opt/webui/build/app/`).

| File | What |
|---|---|
| `docker-compose.yml.j2` | The `fabric-web` container: unprivileged, no ports; config, public CA certs and the fabric-agent socket read-only; creates `web.sock` for nginx in `/opt/webui/run` → `/opt/webui/docker-compose.yml` |
| `webui.json.j2` | The web UI's config: sockets, public URL, CA file, OIDC client (secret inside) → `/opt/webui/config/webui.json` (webui uid, 0400) |
