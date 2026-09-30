# jinja/openbao

Secrets (OpenBao). Rendered by `deploy.py` into `/opt/openbao/`; the `openbao`
systemd unit starts it only when `fabricctl vault unlock` can supply the vault
key (ExecCondition) and wipes the key once it is unsealed.

| File | What |
|---|---|
| `docker-compose.yml.j2` | The `openbao` container (pinned `image_openbao`): config, data (raft), logs, certs and the RAM-only seal key folder mounted; break-glass unix socket for root on the host → `/opt/openbao/docker-compose.yml` |
| `openbao.hcl.j2` | Server config: raft storage, TLS listener (TLS 1.2+, fabric certificate), local unix listener, file audit devices (also read by the log forwarder); the seal itself is in `seal.hcl` beside it, written by fabricctl → `/opt/openbao/config/openbao.hcl` |
