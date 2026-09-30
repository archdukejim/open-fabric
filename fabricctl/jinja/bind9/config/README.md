# jinja/bind9/config

BIND configuration, rendered by `deploy.py` to `/opt/bind9/config/<name>`
(bind-owned, 0640; `named.conf.keys` 0600), mounted read-only at `/etc/bind`
in the container. A change triggers `rndc reconfig` or a restart.

| File | What |
|---|---|
| `named.conf.j2` | Main file: includes the parts below in order (ACLs, keys, TLS, options, logs, zones) → `named.conf` |
| `named.conf.acl.j2` | One `acl` per entry of `bind_acls` → `named.conf.acl` |
| `named.conf.keys.j2` | TSIG keys: every key in `tsig_keys` and, with DHCP DDNS, the `kea-ddns` key; secrets from fabric's secrets → `named.conf.keys` |
| `named.conf.options.j2` | Listeners (53, and the DoH port behind nginx), no recursion, no DNSSEC validation → `named.conf.options` |
| `named.conf.tls.j2` | TLS settings for DoT/DoH (`/etc/bind9/ssl` certificate) → `named.conf.tls` |
| `named.conf.logs.j2` | Logging channels to stderr (the container log, journald) → `named.conf.logs` |
| `named.conf.zones.j2` | Every forward zone in `dns`, the reverse zones, the DHCP subzone; `update-policy` grants per TSIG key → `named.conf.zones` |
| `rndc.key.j2` | The rndc key (`rndc_secret`) → `rndc.key` |
