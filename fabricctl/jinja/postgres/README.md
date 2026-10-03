# jinja/postgres

Keycloak's database (only with `install_keycloak`). Rendered by `deploy.py`.

| File | What |
|---|---|
| `docker-compose.yml.j2` | The `postgres` container (pinned `image_postgres`): TLS on (fabric certificate from `/opt/postgres/certs`), data in `postgres_data_dir`, the Keycloak database password in its environment → `/opt/postgres/docker-compose.yml`, run by the `postgres` systemd unit |
