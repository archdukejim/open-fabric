# Review findings (2026-09-30)

Found while every file was reviewed against the code (the docs suite and
`review-ledger.tsv`). Documentation problems were fixed during the review;
what is listed here needs a code change or an owner decision. Mark items
done in the same change that fixes them (AGENTS.md §3 applies to the DEAD ones).

Paths are relative to `fabricctl/lib/` unless they start with `fabricctl/`,
`webui/`, `installers/` or `tests/`.

## P1 — security, fix first

| # | Where | Finding |
|---|---|---|
| S1 | `deploy.py:425-469` | Everything is rendered into a fixed `/tmp/fabric-render` with the default umask and left there: TSIG/rndc keys, every LDAP role password, the web UI's OIDC secret, compose files with passwords, `rfc2136.ini` — world-readable. A local user can also pre-create the folder and get root (systemd units are copied from it). Only the web UI path is shielded (fabric-agent's PrivateTmp). Fix: `mkdtemp` under umask 077, removed after the deploy. |
| S2 | `fabricctl/jinja/nginx/www/certs/*.sh.j2`, `www/ldap/install-ldap.sh.j2`, `nginx.conf.j2:36` | The CA trust anchor and root-run scripts are fetched over plain HTTP and piped into `sudo bash`, with no fingerprint check: anyone on the LAN can install their own root CA or run code as root. Fix: bake the root SHA-256 into each script and refuse on mismatch; "download, check, run" instead of a pipe. |
| S3 | `fabricctl/jinja/nginx/nginx.conf.j2:171, 282` | `proxy_ssl_verify off` to Step-CA and Keycloak (AGENTS §4). |
| S4 | `setup/backup_install.py`, `cli.py` (reinstall) | `reinstall` leaves `/root/fabric-reinstall-<time>/` forever: plaintext secrets, CA keys, the vault key. |
| S5 | `setup/uninstall.py:311-313` | Uninstall deletes `/opt/<name>` for every TSIG key name: a key named `containerd` wipes an unrelated `/opt/containerd`. |
| S6 | `fabricctl/jinja/dirsrv/seed/00-config.ldif.j2:18`, `30-aci.ldif.j2:9-10` | Anonymous clients can list every user, group, device and role, and who is an admin; `targetattr!=` exposes any attribute added later. |
| S7 | `fabricctl/jinja/keycloak/docker-compose.yml.j2:31-32` | `KC_PROXY_HEADERS` without trusted addresses (any container can spoof X-Forwarded-*); an unused plaintext listener on 8080. |
| S8 | `fabricctl/jinja/bind9/config/named.conf.options.j2`, nginx DoH | DoH queries arrive from nginx's IP, which is in the resolver ACL: anyone reaching 443 can query every zone; all DoH clients share one RRL bucket. |
| S9 | `rbac/required_permission.py` (`POST /v1/apply`) | Apply needs only `dns:write` but runs the whole deployment. |
| S10 | compose files (dirsrv, keycloak, postgres) | Passwords in `environment:` (visible to `docker inspect`); Fluent Bit already uses a 0600 env file. |

## P2 — bugs that break things people will hit

| # | Where | Finding |
|---|---|---|
| B1 | `vault/rotate_vault_key.py:43,60-73` | An interrupted rotation leaves `previous_key_id`; every later rotation is refused forever. |
| B2 | `setup/check_export_dir.py:182` | The export-folder check misses folders uninstall deletes (TSIG key folders, `acme_*`, data dirs outside the base): an export there is deleted with the install. |
| B3 | `setup/run_restore_command.py:37-38` | Restore forwards `--deploy-base` without its value and passes `--no-color`, which setup rejects. |
| B4 | `pki/mint_extra_cert.py`, `setup/mint_extra_certs.py` | A missing `extra_certs` file is re-minted with a new key on every setup — a subordinate CA is silently re-keyed; a missing `out_dir` fails the certs step. |
| B5 | `fabricctl/jinja/vars.yaml.j2` + `logs/deploy_fluentbit.py:49` | Settings not emitted by the template are dropped after the first apply (`ldap_password_min_length`, lockout, `webui_session_*`, `dirsrv_errorlog_level`, `fluentbit_journal`/`extra_files`, `cname_radius`); Fluent Bit is rendered without them at all. |
| B6 | `interactive.py` `apply_mode` | Apply restarts services a second time, `fabric-web` synchronously (can drop the web UI's own request); a failed restart is a traceback. |
| B7 | `dns/remove_acl_entries.py:32` | Removing a key from an ACL comes back on the next apply when the key lists that ACL. |
| B8 | `dns/set_key_acls.py:18` | `!key "x"` is treated as membership. |
| B9 | `dhcp/normalize_dhcp.py:61` | A bad router address crashes apply with a traceback. |
| B10 | `fabricctl/jinja/kea/kea-dhcp4.conf.j2:39` | Kea subnet ids are list positions: reordering subnets misattributes leases. |
| B11 | `fabricctl/jinja/nginx/www/ldap/index.html.j2:53`, `install-certs.sh.j2:102`, `www/manual/index.html.j2:27` | Broken links: the LDAP install script (404), `certificates.<domain>` (does not exist), `lib-doc.md` (now `lib-doc/`). |
| B12 | `setup/run_setup.py:57` | Only `SetupError` is caught: ValidationError/CalledProcessError from several steps end in tracebacks. Same for `vault rotate`, `radius -n`, a few CLI options. |
| B13 | `fabricctl/jinja/openbao/openbao.hcl.j2:39-54` | OpenBao's audit logs are never rotated (grow on the Pi's disk). |
| B14 | `fabricctl/jinja/nginx/nginx.conf.j2:145-173` | Step-CA's vhost terminates TLS: mTLS renew/rekey cannot work through `ca.<domain>:443`. |
| B15 | `fabricctl/jinja/bind9/data/zone.j2:18,27` | A domain zone without `zone_authority` gets `NS ns.<domain>` with no address for it. |
| B16 | `webui/views.py:64`, `webui/server.py:624` | The Audit log link shows to everyone (403 for most); custom bundles with `pki:sign` but no `devices:read` get 403 on sign/issue. |
| B17 | `cli.py:93` | `fabricctl --help` refuses non-root users. |
| B18 | `fabricctl/jinja/systemd/fabric-agent.service.j2` | `IPAddressDeny=any` likely blocks adding a KMIP HSM on the LAN from the web UI (only tested against a local PyKMIP). |

## P3 — AGENTS.md rules not met

| # | Where | Finding |
|---|---|---|
| R1 | compose templates | No memory limit by default (bind9, dirsrv, nginx, step-ca, keycloak, postgres, fabric-web) — only under some `host_ram_capacity` values (§5). |
| R2 | `system/service_status.py`, vars `security` | Relaxations (firewall off, `firewall_allow`, Docker hardening off, `message_authenticator: false`) are not shown by `fabricctl status` or the dashboard (§4); `vars.yaml.j2` says they are. |
| R3 | local image builds | `apt-get install` of unpinned packages (and Kea's key fetched) at build time; no offline or mirror path (§4, §5). |
| R4 | design D14/D11 | The decided privilege model (CLI → agent socket, `fabric-admins`) and userns-remap are marked decided but not built — build them or record the current model. |
| R5 | CLI audit | Every CLI change is audited as `root`, not the sudo user (`common/sudo_owner.py` exists). |

## P4 — lower-risk security and robustness

- `webui/server.py:509` `next=` accepts control characters (possible open redirect after sign-in, unverified); `webui/server.py:513` unbounded pending logins for 10 min.
- `webui/oidc.py:222-228` some malformed tokens raise the wrong error type (still refused).
- `fabricctl/jinja/freeradius/python/fabric_radius.py:85,146` unauthenticated User-Name goes into the decision log unescaped (log-line forging).
- `vault/add_usb_slot.py:64` a failed USB enrolment leaves the key on the stick; `vault/add_kmip_slot.py:21` KMIP client key briefly on disk-backed `/tmp`.
- `fabricctl/jinja/stepca/leaf.tpl.j2:14-15` every leaf gets `clientAuth`: the web UI's mTLS gate accepts service and device certificates (the CN must still match the user).
- `pki/sign_csr.py:63` signing for a device links it without `pki:link-device` (custom bundles only).
- `fabricctl/jinja/kea/kea-dhcp-ddns.conf.j2:9` the DDNS listener on fabric_net is unauthenticated.
- `fabricctl/jinja/postgres/docker-compose.yml.j2` accepts non-TLS connections.
- nginx: port 80 on all interfaces, no `default_server` for unknown SNI, TLS settings not uniform; Fluent Bit's HTTP server on 2020 unused; weak healthchecks.
- Templates insert values unescaped into pages and shell scripts; `install-certs.sh` predictable temp file; the LDAP client script lets every directory user log in.
- `secrets/save_secrets.py:56` rewrites the only secrets file in place (not atomic); `secrets show radius_secrets` prints all at once.
- `dns/*` minor: `/opt` hard-coded for `rfc2136.ini`, quoted `key "x"` refused, CNAME beside A allowed; `radius/map_radius_group.py:27` unstripped name.
- Vendored `marked`/`mermaid` have no source URL or checksum; the manual publishes all of `docs/` unauthenticated.
- `fabricctl/jinja/freeradius/config/mods/eap.j2`: TLS max 1.2, deprecated options, no CRL/OCSP (revocation = unlinking).
- `images/switch_image.py:51` rollback only for some exception types.

## P5 — dead code (AGENTS §3: delete, or register as stale)

- Settings nothing reads: `cert_root_*`, `cert_intermediate_*` (8, never passed to Step-CA), `system_timezone`, `service_dirs`, `compose_file`/`project_containers` (menu only).
- `setup/context.py` `SetupContext.enabled` and the `secrets` setter; `setup/verify_install.py` `_curl(client_cert)`.
- `logs/deploy_fluentbit.py:7` `_write` duplicates `common/write_file_if_changed` (without the chmod).
- `keycloak/require_password_change.py`, `user_has_role.py` build their own admin client instead of `keycloak_admin()`.
- `setup/uninstall.py` old `webui` unit and `fabric/webui:local` image names.
- `fabricctl/jinja/bind9/config/named.conf.tls.j2` unused `tls` profile and the empty `bind9/ssl` mount; nginx `conf.d` include; `modconfdir`.
- `.gitignore` Ansible-era entries.

## Test gaps (tests/README.md is honest about what each suite proves)

- Never asserted: the host firewall and Docker daemon hardening, certificate renewal, the offline path, relaxations in `status`, arm64 images, `needs_rebuild` on a new base.
- Only in their own suites (not in the full install): EAP-TLS, log forwarding; the web UI's Kea/RADIUS pages against a real agent.
- Weak checks: `tests/freeradius/run.py:397` (PAP outside the tunnel uses a wrong password), `:433` and `tests/kea/run.py:194` (hardening checks inspect flags the test itself set), `tests/dirsrv/run.sh:74` (TLS < 1.2 may be refused by the client), `tests/fluentbit/run.py` logs-status counter (fails consistently: investigate).
- Intermittent service starts (2026-09-30 / 10-01, each passed on rerun, none tied to the change under test): `dirsrv` "Can't contact LDAP server" while seeding in `hardening`; `systemctl start postgres` failing during the sandbox's reinstall; `systemctl start nginx` failing during the sandbox's image rollback. Likely a start racing a container that is still stopping or a slow host; capture `journalctl -u <unit>` on failure in the suites, then fix the start path (`start_unit`, the wrapper unit's health wait).

## Decisions for the owner

- OpenBao first in setup (D26?) — secrets straight into OpenBao at install; needs a temporary TLS bootstrap before Step-CA. Does not remove secrets from service configs (S1, S10 do that).
- `POST /v1/apply` (S9): its own permission, e.g. `system:apply`, or `system:admin`.
- `system:admin` has no route today; what should it grant?
- Plain-HTTP CA bootstrap (S2): keep a HTTP path for first contact, with fingerprint pinning, or HTTPS only?
- The design's privilege model (R4): build it or adopt the current one.
