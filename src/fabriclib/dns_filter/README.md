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
| `ensure_dnslog_db.py` | The query log's database in fabric's Postgres: its own role and database, its tables |
| `ingest_dns_log.py` | Read the resolver's new log lines into the query log, mark rewrites, recompute the statistics, purge |
| `read_query_log.py` | Search the query log (client, name, blocked only), read up to the moment first |
| `dns_filter_stats.py` | The statistics: the last 24 hours, the last 7 days, per list and rules zone, the most blocked names |
| `filter_overview.py` | The DNS filter for the web console: its settings, each list's state, the statistics |
| `show_filter_status.py` | Each list's state and the resolver's, for `fabricctl dns-filter status` |
| `run_dns_filter_command.py` | `fabricctl dns-filter lists \| status \| log \| stats \| ingest` |
| `common/` | Helpers shared by these files |
