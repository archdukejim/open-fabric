# jinja/nginx

The reverse proxy and fabric's static pages. Rendered and copied by
`deploy.py` into `/opt/nginx/`; the `nginx` systemd unit runs it.

| Path | What |
|---|---|
| `docker-compose.yml.j2` | The `nginx` container (pinned `image_nginx`): config, certs and `www/` mounted read-only, the web UI's socket dir at `/srv/webui` → `/opt/nginx/docker-compose.yml` |
| `nginx.conf.j2` | Port 80 (health, `/certs/`, redirect to HTTPS); HTTPS virtual hosts for DoH (bind9), step-ca, the landing page (with `/manual/`), certs (with `join-linux.sh`), OpenBao, Keycloak and the Fabric web UI (client certificate required); LDAP 389/636 as TCP passthrough to 389-DS → `/opt/nginx/config/nginx.conf` |
| [www/](www/) | The static pages served from `/srv/www` → `/opt/nginx/www/` |
