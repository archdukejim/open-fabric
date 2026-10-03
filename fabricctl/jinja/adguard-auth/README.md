# jinja/adguard-auth

The sign-in in front of the optional DNS filter's UI (design [dns-filter.md](../../../docs/design/dns-filter.md) §5),
a unit of its own (`adguard-auth`) so that AdGuard's DNS never depends on it or on Keycloak; only with `dns_filter: adguard`.

| File | What |
|---|---|
| `docker-compose.yml.j2` | oauth2-proxy (pinned digest, no capabilities, read-only) on fabric_net; its configuration, secrets and the fabric root CA are mounted from `/opt/adguard/oauth2-proxy` → `/opt/adguard-auth/docker-compose.yml` |
