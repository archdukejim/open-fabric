# jinja/fluentbit

Optional log forwarding (Fluent Bit, design 2.1.15.1; only with `install_fluentbit`).
The compose file is rendered by `deploy.py`; the config by
`fabriclib/logs/deploy_fluentbit.py`. The `fluentbit` systemd unit runs it.

| File | What |
|---|---|
| `docker-compose.yml.j2` | The `fluentbit` container (pinned `image_fluentbit`): reads the host journal and OpenBao's audit log read-only, credentials from `config/secrets.env` → `/opt/fluentbit/docker-compose.yml` |
| `fluent-bit.yaml.j2` | Inputs (journal, OpenBao audit log) and outputs (syslog and/or Elasticsearch/OpenSearch, verified TLS) from `log_forwarding` → `/opt/fluentbit/config/fluent-bit.yaml` (root:fluentbit 0640) |
