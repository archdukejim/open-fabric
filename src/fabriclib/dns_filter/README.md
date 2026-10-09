# fabriclib/dns_filter

The DNS filter, a BIND resolver filtering with response policy zones (design
[1.12.2](../../../docs/volume_1_description_and_architecture/1.12.2-bind-resolver.md#11221-status); it replaced AdGuard
Home in 0.7, decision 2.1.12.3).

| File | What |
|---|---|
| `convert_list.py` | A published block list (hosts, domains, RPZ, AdGuard DNS syntax) as a response policy zone; what cannot be converted is counted |
| `update_lists.py` | Fetch, convert and check the lists; write the changed zones and reload them in the resolver; keep each list's state |
| `deploy_resolver.py` | Deploy step: the resolver's folders, configuration, fabric's and the owner's rules zones, control key; fetch a list never fetched |
| `check_filter_settings.py` | Refuse resolver settings that cannot work: lists, allows and blocks, upstreams |
| `import_adguard_settings.py` | 0.6's AdGuard Home settings as the resolver's (upgrade to 0.7): upstreams, lists, rules; what cannot move is listed |
| `show_filter_status.py` | Each list's state and the resolver's, for `fabricctl dns-filter status` |
| `run_dns_filter_command.py` | `fabricctl dns-filter lists \| status` |
| `common/` | Helpers shared by these files |
