# jinja/keycloak

SSO (Keycloak; only with `install_keycloak`, together with postgres/).
Rendered by `deploy.py` into `/opt/keycloak/`; the `keycloak` systemd unit
runs it after `postgres`.

| Path | What |
|---|---|
| `docker-compose.yml.j2` | The `keycloak` container (`fabric/keycloak:local`, `start --optimized`, read-only root): database settings, bootstrap admin, data dir `keycloak_data_dir`, certificates from `/opt/keycloak/certs` → `/opt/keycloak/docker-compose.yml` |
| [`packaging/images/keycloak/`](../../packaging/images/keycloak/) | The pre-built ("optimized") local image on the pinned `image_keycloak` → `/opt/keycloak/build/` (installed as `build/`) |
