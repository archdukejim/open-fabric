# tests

Suites prove behaviour against real containers ([4.8.2](../docs/volume_4_infrequent_ops/4.8.2-automated-tests.md#482-automated-tests)). Run them with
`sudo tests/run-all.sh [suite ...]` (all but `sandbox` by default); each suite
writes its log to `$FABRIC_TEST_OUT` (default `/tmp/fabric-tests`). The `docs`
suite needs no Docker or root and also runs alone: `python3 tests/docs/run.py`.

| Suite | Where | What it proves |
|---|---|---|
| `docs` | [docs/](docs/) | Every function documented (Purpose/Inputs/Returns/Fails/Feeds), the function reference (manual 1.11) current, docs and code agree, every file reviewed |
| `lint` | [lint/](lint/) | ruff (Python, `pyproject.toml`) and shellcheck (shell) from their pinned images: no findings in `src/`, `scripts/`, `tests/` (decision D34) |
| `consent` | [consent/](consent/) | Asking before fabric changes the host: answers, questions, the subset rule, declined groups, the `fabric-*` accounts and their move, no containers |
| `render` | `render.py` | Every template renders from `vars.yaml.j2`; security properties of the rendered configs; every module imports |
| `nginx` | `nginx_check.sh` | The rendered nginx configuration passes `nginx -t` in the pinned image |
| `zone` | `zone_test.py` | `deploy.py`'s zone deployment with `rndc` stubbed: unchanged records ignored, changed zones found, fresh mtime, BIND's late write detected and the swap repeated, stale journal removed |
| `webui` | [webui/](webui/) | The web UI container against a mock Keycloak and the real fabric-agent; the dev preview |
| `pki` | [pki/](pki/) | Manual PKI against a real Step-CA |
| `adguard` | [adguard/](adguard/) | The DNS filter: AdGuard Home from fabric's generated config in front of BIND (real containers): resolution, rules, auth, the merge that keeps UI edits |
| `ntp` | [ntp/](ntp/) | Time: chrony from fabric's generated config (real containers): serving the LAN and refusing others, a site syncing from its upstream site, the settings and what they refuse |
| `federation` | [federation/](federation/) | Invitations, the federation endpoint, a site joining an upstream (real Step-CA) and directory replication between two real 389-DS (M5) |
| `openbao` | [openbao/](openbao/) | OpenBao: unlock methods (key file, USB, security key, KMIP), rotation, fabric's secrets, policies, break glass |
| `fluentbit` | [fluentbit/](fluentbit/) | Log forwarding to TLS syslog and Elasticsearch receivers |
| `kea` | [kea/](kea/) | Kea DHCP with DDNS into BIND, real DHCP clients |
| `freeradius` | [freeradius/](freeradius/) | 802.1X against a real 389-DS: EAP-TLS, EAP-TTLS, MAB, refusals |
| `samba` | [samba/](samba/) | The Windows domain controller: settings (D87, D89), the rendered container, what changes around it; a real DC converged twice, the policy, the GPOs, BIND serving the AD zone through DLZ with signed updates, and the refusals (unsigned updates, another site, service accounts, short or wrong passwords) |
| `dirsrv` | [dirsrv/](dirsrv/) | 389 Directory Server: seed, TLS, ACIs, the admin user, device RBAC |
| `keycloak` | [keycloak/](keycloak/) | Keycloak on fabric's directory (Samba AD): bootstrap twice, AD federation, a first sign-in through TOTP and a new password that lands in AD, refusals |
| `hardening` | [hardening/](hardening/) | The core services and OpenBao started from their real compose files work and are hardened |
| `images` | [images/](images/) | fabric's own images build from `packaging/docker-bake.hcl` with a default host's build inputs and pass the smoke test CI runs before publishing (decision D41) |
| `sandbox` | [sandbox/](sandbox/) | A full install from the .deb in a disposable systemd + Docker container (about 30 min; not in the default list) |

Not in `run-all.sh`: [host/](host/) (a subset of the sandbox checks on a real machine over SSH).

| File | What |
|---|---|
| `run-all.sh` | Run suites, report PASS/FAIL per suite |
| `render.py` | The `render` suite |
| `nginx_check.sh` | The `nginx` suite |
| `zone_test.py` | The `zone` suite |
| `image_ref.py` | Print the validated, digest-pinned ref of one image (suites test exactly what fabric runs) |
