# fabriclib/dns_filter

The DNS filter, a BIND resolver filtering with response policy zones (design
[1.12.2](../../../docs/volume_1_description_and_architecture/1.12.2-bind-resolver.md#11221-status); it replaced AdGuard
Home in 0.7, decision 2.1.12.3).

| File | What |
|---|---|
| `convert_list.py` | A published block list (hosts, domains, RPZ, AdGuard DNS syntax) as a response policy zone; what cannot be converted is counted |
| `update_lists.py` | Fetch, convert and check the lists; write the changed zones and reload them in the resolver; keep each list's state |
| `deploy_resolver.py` | Deploy step: the resolver's folders, configuration (the main view and each client group's chained view), the rules zones (fabric's, the owner's, each group's, safe search), control key; fetch a list never fetched |
| `resolver_views.py` | What each view loads: everyone's lists, each group's match-clients (the most specific address wins), rules, safe search and own lists; the memory guard |
| `check_filter_settings.py` | Refuse resolver settings that cannot work: lists, allows and blocks, upstreams, safe search, groups |
| `check_filter_groups.py` | Refuse client groups that cannot work: names, clients, safe search, their own lists and rules |
| `expand_group_clients.py` | A group's `dhcp:`, `device:` and `vlan:` clients turned into addresses from Kea's settings on every apply (manual 1.10.3.7) |
| `import_adguard_settings.py` | 0.6's AdGuard Home settings as the resolver's (upgrade to 0.7): upstreams, lists, rules, safe search, persistent clients as groups; what cannot move is listed |
| `ensure_dnslog_db.py` | The query log's database in fabric's Postgres: its own role and database, its tables |
| `ingest_dns_log.py` | Read the resolver's new log lines into the query log, mark rewrites, recompute the statistics, purge |
| `read_query_log.py` | Search the query log (client, name, blocked only), read up to the moment first |
| `dns_filter_stats.py` | The statistics: the last 24 hours, the last 7 days, per list and rules zone, the most blocked names |
| `filter_overview.py` | The DNS filter for the web console: its settings, each list's state, the groups, safe search and the sites it covers, the statistics |
| `add_filter_list.py` | Add a block list, for everyone or a group (vars.yaml); fetched by the lists job |
| `remove_filter_list.py` | Take a block list out, everyone's or a group's (vars.yaml) |
| `add_filter_rule.py` | Allow or block a name and every name below it, for everyone or a group; a name in the other rule moves |
| `remove_filter_rule.py` | Take a name out of the allows or blocks, everyone's or a group's |
| `set_filter_group.py` | Add a client group, or change its addresses and subnets |
| `remove_filter_group.py` | Remove a client group: its clients are answered as everyone |
| `set_safe_search.py` | Strict safe search on or off, YouTube strict or moderate, for everyone or a group |
| `set_filter_upstreams.py` | The DoT upstreams (address and certificate name pairs), or none: the root servers |
| `fetch_catalogue.py` | AdGuard's list catalogue, read from its registry and kept for the web console |
| `refresh_lists.py` | The lists job: fetch the lists and the catalogue, apply a list not in use yet |
| `start_list_fetch.py` | Start the lists job now (fabric-agent has no internet) |
| `show_filter_status.py` | Each list's state and the resolver's, for `fabricctl dns-filter status` |
| `run_dns_filter_command.py` | `fabricctl dns-filter lists \| status \| log \| stats \| ingest` |
| `resolver_tls_pending.py` | Whether the DNS name's certificate arrived after the resolver was rendered (setup renders once more) |
| `common/` | Helpers shared by these files |
