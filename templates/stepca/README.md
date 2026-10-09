# jinja/stepca

The CA (step-ca). Rendered by `deploy.py`; the `stepca` systemd unit runs the
`step-ca` container. The CA's own state in `/opt/stepca/data` is created by
setup (`fabriclib/setup/init_pki.py`); its `ca.json` is converged on every setup run.

| Path | What |
|---|---|
| `docker-compose.yml.j2` | The `step-ca` container (`fabric/stepca:local`), `/opt/stepca/data` at `/home/step`, password file from `secrets/`, healthcheck `step ca health` → `/opt/stepca/docker-compose.yml` |
| `leaf.tpl.j2` | x509 template for leaf certificates (Go template passed through Jinja raw blocks) → `/opt/stepca/data/templates/certs/leaf.tpl` |
| `acme.tpl.j2` | x509 template for the ACME provisioner: names under the domain only, no addresses (it fails otherwise), the CRL distribution point (2.1.5.8) → `/opt/stepca/data/templates/certs/acme.tpl` |
| `subca.tpl.j2` | x509 template for subordinate CAs (`--set pathLen=<N>`) → `/opt/stepca/data/templates/certs/subca.tpl` |
| [`packaging/images/stepca/`](../../packaging/images/stepca/) | The local image that drops the upstream binary's file capability → `/opt/stepca/build/` (installed as `build/`) |
