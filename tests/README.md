# tests

Suites prove behaviour against real containers (AGENTS.md §6). Run them with
`sudo tests/run-all.sh [suite ...]` (all but `sandbox` by default); each suite
writes its log to `$FABRIC_TEST_OUT` (default `/tmp/fabric-tests`). The `docs`
suite needs no Docker or root and also runs alone: `python3 tests/docs/run.py`.

| Suite | Where | What it proves |
|---|---|---|
| `docs` | [docs/](docs/) | Every function documented (Purpose/Inputs/Returns/Fails/Feeds), `docs/lib-doc/` current, docs and code agree, every file reviewed |
| `render` | `render.py` | Every template renders from `vars.yaml.j2`; security properties of the rendered configs; every module imports |
| `nginx` | `nginx_check.sh` | The rendered nginx configuration passes `nginx -t` in the pinned image |
| `zone` | `zone_test.py` | `deploy.py`'s zone deployment with `rndc` stubbed: unchanged records ignored, changed zones found, fresh mtime, BIND's late write detected and the swap repeated, stale journal removed |
| `webui` | [webui/](webui/) | The web UI container against a mock Keycloak and the real fabric-agent; the dev preview |
| `pki` | [pki/](pki/) | Manual PKI against a real Step-CA |
| `openbao` | [openbao/](openbao/) | OpenBao: unlock methods (key file, USB, security key, KMIP), rotation, fabric's secrets, policies, break glass |
| `fluentbit` | [fluentbit/](fluentbit/) | Log forwarding to TLS syslog and Elasticsearch receivers |
| `kea` | [kea/](kea/) | Kea DHCP with DDNS into BIND, real DHCP clients |
| `freeradius` | [freeradius/](freeradius/) | 802.1X against a real 389-DS: EAP-TLS, EAP-TTLS, MAB, refusals |
| `dirsrv` | [dirsrv/](dirsrv/) | 389 Directory Server: seed, TLS, ACIs, the admin user, device RBAC |
| `keycloak` | [keycloak/](keycloak/) | Keycloak bootstrap against the dirsrv suite's directory |
| `hardening` | [hardening/](hardening/) | The core services and OpenBao started from their real compose files work and are hardened |
| `sandbox` | [sandbox/](sandbox/) | A full install from the .deb in a disposable systemd + Docker container (about 30 min; not in the default list) |

Not in `run-all.sh`: [host/](host/) (a subset of the sandbox checks on a real machine over SSH).

| File | What |
|---|---|
| `run-all.sh` | Run suites, report PASS/FAIL per suite |
| `render.py` | The `render` suite |
| `nginx_check.sh` | The `nginx` suite |
| `zone_test.py` | The `zone` suite |
| `image_ref.py` | Print the validated, digest-pinned ref of one image (suites test exactly what fabric runs) |
