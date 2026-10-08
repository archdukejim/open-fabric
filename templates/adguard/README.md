# jinja/adguard

The optional DNS filter (design [1.12.1](../../docs/volume_1_description_and_architecture/1.12.1-adguard.md#11211-status)); only with `dns_filter: adguard`.

| File | What |
|---|---|
| `docker-compose.yml.j2` | AdGuard Home (`fabric/adguard:local`, no capabilities, `host_ip:53` → 5300 inside, UI not published) → `/opt/adguard/docker-compose.yml`; its sign-in is the separate unit in [../adguard-auth/](../adguard-auth/) |
| [`packaging/images/adguard/`](../../packaging/images/adguard/) | The image: AdGuard Home FROM the pinned digest, its binary copied without file capabilities so it runs with none |
| `AdGuardHome.base.yaml` | The starting configuration when an install has none (from the owner's setup, without upstreams or lists: local DNS only); fabric's keys are filled in by `fabriclib/dns_filter/build_adguard_config.py` |
| `oauth2-proxy.cfg.j2` | oauth2-proxy (unit `adguard-auth`): OIDC against the site's Keycloak with its endpoints given (no discovery at start, so it starts while Keycloak is down), `fabric:dns:filter` required, secrets from `secrets.env` → `/opt/adguard/oauth2-proxy/oauth2-proxy.cfg` |
