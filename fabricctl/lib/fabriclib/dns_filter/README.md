# fabriclib/dns_filter

The optional DNS filter in front of BIND (design [dns-filter.md](../../../../docs/design/dns-filter.md)).

| File | What |
|---|---|
| `build_adguard_config.py` | AdGuard Home's configuration with fabric's keys set (upstreams, rules, clients, its local user) and everything changed in its UI kept |
| `deploy_adguard.py` | Deploy step: AdGuard's config (merged, rewritten only on a real change), oauth2-proxy's settings and secrets, nginx's sign-in snippet |
