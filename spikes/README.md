# spikes

Throwaway spikes that answer a design question before the design is complete (global Rule 4). Never merged into
`src/`; their outcomes are recorded in Volume 2.

| Path | What |
|---|---|
| [samba/](samba/) | The S0 spike: Samba AD replacing 389-DS (manual 2.3.6.1) |
| [kerberos-sso/](kerberos-sso/) | Spike K1: Kerberos sign-in to Keycloak with a keytab from fabric's Samba DC (manual 2.3.6.2.8) |
| [postgres-nginx/](postgres-nginx/) | 2.1.9.14's question: Postgres replicating between sites through nginx's stream proxy, never on the host (manual 2.3.6.1.25) |
| [dns-filter/](dns-filter/) | 2.1.12.3's spike: BIND 9.20 as the filtering resolver — AdGuard's lists converted to RPZ, groups as chained views, DoT, safe search (manual 2.3.12.1.16) |
