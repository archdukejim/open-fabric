# fabriclib/dns_filter/common

Helpers shared by the DNS filter's files (manual [1.12.2](../../../../docs/volume_1_description_and_architecture/1.12.2-bind-resolver.md#11221-status)).

| File | What |
|---|---|
| `filter_zones.py` | fabric's own zones: forwarded to this site's BIND and never filtered |
| `list_zone.py` | A list's zone name, from its URL (stable when lists are reordered or renamed) |
| `resolver_paths.py` | The resolver's folders and files under the deploy base |
| `resolver_rndc.py` | Run rndc in the resolver's container, with its own control key |
