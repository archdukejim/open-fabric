# spikes/postgres-nginx

D104's question (manual 1.8.8.16, S8.6): can a site's Postgres replicate to another site's while Postgres is never on
the host? Throwaway (global Rule 4); its outcome is in manual 5.8.1.25.

| File | What |
|---|---|
| `run.sh` | Two Postgres servers and nginx's stream proxy in front of one, with a test CA: direct TLS through nginx with a required client certificate, the refusals, logical replication with a row filter; the inner hop as a shared Unix socket (default), TLS (refused by nginx) or plain |
