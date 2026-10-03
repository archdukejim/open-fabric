# jinja/stepca

The CA (step-ca). Rendered by `deploy.py`; the `stepca` systemd unit runs the
`step-ca` container. The CA's own state in `/opt/stepca/data` is created by
setup (`fabriclib/setup/init_pki.py`) and never re-rendered.

| Path | What |
|---|---|
| `docker-compose.yml.j2` | The `step-ca` container (`fabric/stepca:local`), `/opt/stepca/data` at `/home/step`, password file from `secrets/`, healthcheck `step ca health` → `/opt/stepca/docker-compose.yml` |
| `leaf.tpl.j2` | x509 template for leaf certificates (Go template passed through Jinja raw blocks) → `/opt/stepca/data/templates/certs/leaf.tpl` |
| `subca.tpl.j2` | x509 template for subordinate CAs (`--set pathLen=<N>`) → `/opt/stepca/data/templates/certs/subca.tpl` |
| [`packaging/images/stepca/`](../../packaging/images/stepca/) | The local image that drops the upstream binary's file capability → `/opt/stepca/build/` (installed as `build/`) |
