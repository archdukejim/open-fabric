# jinja/bind9

Authoritative DNS (BIND 9 from Debian packages). Rendered by `deploy.py`
(`apply_deployment`) into `/opt/bind9/`; the `bind9` systemd unit runs it.

| Path | What |
|---|---|
| `docker-compose.yml.j2` | The `bind9` container (`fabric/bind9:local`): runs as bind, no capabilities; mounts `config/` at `/etc/bind`, `data/` at `/var/lib/bind` → `/opt/bind9/docker-compose.yml` |
| [build/](build/) | The local image: Debian's bind9 on the pinned Debian base → `/opt/bind9/build/` |
| [config/](config/) | `named.conf` and its included parts, `rndc.key` → `/opt/bind9/config/` |
| [data/](data/) | Zone file templates (forward and reverse) → `/opt/bind9/data/db.<zone>` |
