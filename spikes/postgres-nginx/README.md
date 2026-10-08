# spikes/postgres-nginx

2.1.9.14's question (manual 1.9.8.16, S8.6): can a site's Postgres replicate to another site's while Postgres is never on
the host? Throwaway (global Rule 4); its outcome is in manual 2.3.6.1.25.

| File | What |
|---|---|
| `run.sh` | Two Postgres servers and nginx's stream proxy in front of one, with a test CA: direct TLS through nginx with a required client certificate, the refusals, logical replication with a row filter; the inner hop as a shared Unix socket (default), TLS (refused by nginx) or plain |
