# tests/resolver

The DNS filter's BIND resolver (manual [1.12.2](../../docs/volume_1_description_and_architecture/1.12.2-bind-resolver.md#11221-status))
with real containers.

| File | What |
|---|---|
| `run.py` | The converter's cases, the settings that must be refused, then fabric's BIND image as the authoritative server and the resolver run as its rendered compose file says: a client outside the allowed networks refused, fabric's zone never filtered, lists and the owner's rules applied, the logs, a reload, the list job (a changed list reloaded alone, a failed list kept apart), DoT upstream when Cloudflare is reachable; the query-log job parses every line BIND wrote |
| `querylog.py` | The query log and statistics with a real Postgres: ingesting, rewrites marking their queries, reading on (a rotated file, Postgres down), purging at 7 days while statistics stay, searches, refused input, the database's isolation, the admin-only permission |
