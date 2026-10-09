# fabriclib/dns_filter

The DNS filter (design [1.12](../../../docs/volume_1_description_and_architecture/1.12.2-bind-resolver.md#11221-status)):
AdGuard Home in front of BIND (1.12.1), and the BIND resolver that replaces it in 0.7 (1.12.2).

| File | What |
|---|---|
| `build_adguard_config.py` | AdGuard Home's configuration with fabric's keys set (upstreams, rules, clients, its local user) and everything changed in its UI kept |
| `deploy_adguard.py` | Deploy step: AdGuard's config (merged, rewritten only on a real change), oauth2-proxy's settings and secrets, nginx's sign-in snippet |
| `convert_list.py` | A published block list (hosts, domains, RPZ, AdGuard DNS syntax) as a response policy zone; what cannot be converted is counted |
| `update_lists.py` | Fetch, convert and check the lists; write the changed zones and reload them in the resolver; keep each list's state |
| `deploy_resolver.py` | Deploy step: the resolver's folders, configuration, fabric's and the owner's rules zones, control key; fetch a list never fetched |
| `check_filter_settings.py` | Refuse resolver settings that cannot work: lists, allows and blocks, upstreams |
| `show_filter_status.py` | Each list's state and the resolver's, for `fabricctl dns-filter status` |
| `run_dns_filter_command.py` | `fabricctl dns-filter lists \| status` |
| `common/` | Helpers shared by these files |
