# jinja/chrony

Time on the host (design [1.13.1](../../docs/volume_1_description_and_architecture/1.13.1-chrony.md#11311-status)); rendered by `fabriclib/ntp/deploy_chrony.py`, not a container.

| File | What |
|---|---|
| `chrony.conf.j2` | chrony: the upstream site first, then `ntp_servers` (NTS where marked); the networks it answers, rate-limited; its own clock as the last resort (`local stratum 10 orphan`); chronyc from this host only → `/etc/chrony/chrony.conf` |
