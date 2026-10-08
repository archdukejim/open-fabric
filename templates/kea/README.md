# jinja/kea

Optional DHCP (Kea 3.0 LTS, design §5; only with `install_kea`). The compose
file is rendered by `deploy.py`; the configs by `fabriclib/dhcp/deploy_kea.py`
into `/opt/kea/config/` (root:kea 0640). The `kea` systemd unit runs both
containers.

| Path | What |
|---|---|
| `docker-compose.yml.j2` | Two containers from `image_kea` (default `fabric/kea:local`): `kea-dhcp4` on the host network with only the raw-socket and port-67 capabilities, and `kea-ddns` on fabric_net → `/opt/kea/docker-compose.yml` |
| `kea-dhcp4.conf.j2` | DHCPv4 server from `dhcp:` in vars.yaml: interface, subnets, pools, options, reservations, lease file, DDNS → `/opt/kea/config/kea-dhcp4.conf` |
| `kea-dhcp-ddns.conf.j2` | DHCP-DDNS: updates only `<ddns_subdomain>.<domain>` in bind9 with the `kea-ddns` TSIG key (secret inside, design 2.1.4.1) → `/opt/kea/config/kea-dhcp-ddns.conf` |
| [`packaging/images/kea/`](../../packaging/images/kea/) | The local image: Kea from ISC's signed repository, version pinned in images.lock.yaml → `/opt/kea/build/` (installed as `build/`) |
