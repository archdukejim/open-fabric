# fabriclib/dns_filter/common

Helpers shared by the DNS filter's files (manual [1.12.2](../../../../docs/volume_1_description_and_architecture/1.12.2-bind-resolver.md#11221-status)).

| File | What |
|---|---|
| `filter_zones.py` | fabric's own zones: forwarded to this site's BIND and never filtered |
| `list_zone.py` | A list's zone name, from its URL (stable when lists are reordered or renamed) |
| `resolver_paths.py` | The resolver's folders and files under the deploy base |
| `dnslog_psql.py` | SQL for the query log through psql in the Postgres container (local socket, SQL on stdin) |
| `resolver_rndc.py` | Run rndc in the resolver's container, with its own control key |
| `all_lists.py` | Every list in use: everyone's, then each group's own, once each |
| `rule_names.py` | One allow or block setting checked and normalised; what a name may be (`NAME_RE`) |
| `filter_target.py` | Where a change goes: everyone's settings or one client group's |
| `safe_search.py` | Safe search's table (engines, names, enforced answers) for the zones and the console |
