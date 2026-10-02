# jinja/chrony

Time on the host (design [ntp.md](../../../docs/design/ntp.md)); rendered by `fabriclib/ntp/deploy_chrony.py`, not a container.

| File | What |
|---|---|
| `chrony.conf.j2` | chrony: the upstream site first, then `ntp_servers` (NTS where marked); the networks it answers, rate-limited; its own clock as the last resort (`local stratum 10 orphan`); chronyc from this host only → `/etc/chrony/chrony.conf` |
