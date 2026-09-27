# Stale code register

Code that is unused, duplicated or superseded but **might still have value**,
kept here for an owner decision (see [AGENTS.md](../../AGENTS.md) §3). Code
with no value is deleted immediately instead and noted in the commit.

Status: `open` (awaiting decision) · `planned` (removal/rework scheduled) ·
`done` (resolved — keep the row for history).

| ID | Path | What / why stale | Possible value | Recommendation | Found | Status |
|---|---|---|---|---|---|---|
| S1 | `fabric/lib/package.sh` | Offline bundler (apt .debs, Ansible collections, Docker images, ClamAV scan). **Orphaned**: nothing sources or calls it since the `offline.sh` wrapper was removed. Its `CONTEXT_IMAGES` additions (dirsrv, webui) are therefore unreachable; `BUILT_IMAGES` is an empty, unused mechanism. | Basis for `fabricctl images export/import` and offline host-package bundles (design §7b, phase 0.6). | Port the image export/scan parts into `fabricctl images/` (one function per file); drop controller/Ansible parts when Ansible is removed; then delete. | 2026-09-27 | open |
| S2 | `fabric/lib/prereqs.sh` | Installs a local offline prerequisites bundle. **Orphaned** (no callers). | Offline install of host packages. | Superseded by `.deb` `Depends:` + an offline apt bundle (phase 2). Delete then, unless you want it back sooner. | 2026-09-27 | open |
| S3 | `fabric/lib/archive.sh` | Snapshot / list / export helpers. **Orphaned** (no callers); reads a `.version` file nothing writes and calls an undefined `read_version_file`. Overlaps `reinstall_backup.sh` / `reinstall_restore.sh`. | Pre-upgrade snapshots and rollback of config + data. | Decide: fold into a `fabricctl backup/` domain (snapshot before every update/migration), or delete. | 2026-09-27 | open |
| S4 | `README.md` (Deployment Modes), `docs/ansible-doc.md`, `docs/lib-doc.md` | Describe an `offline.sh` wrapper that no longer exists. | — | Rewrite with the decision on S1/S2 (point at `fabricctl images export/import`). | 2026-09-27 | open |
| S5 | DNS record editing — `fabric/lib/dns.sh` + `vars.sh` (`fabricctl --dns-record`), `interactive.py` (`edit_dns_zone`), `fabric/lib/agent/actions.py` | **Three implementations** of add/remove record. Only the agent one validates names/values (the others accept anything an admin types, including zone-file syntax). | The validated version is the one to keep. | Consolidate into `dns/add_record.py`, `dns/remove_record.py`, `dns/list_zones.py` (+ shared validation), used by the CLI, the interactive editor and fabricd; delete the rest. | 2026-09-27 | planned (phase 1) |
| S6 | Certificate minting — `fabric/lib/certs.sh` (`_mint_extra_cert`), `fabric/lib/services.sh` (`run_service_certs`), `fabric/playbooks/08-mint-service-certs.yml` | **Three implementations** of issuing service/extra certs via Step-CA, with slightly different options (key size, template, install paths). | One `pki/` domain: `mint_service_cert`, `mint_client_cert`, `install_cert`. | Consolidate when porting playbook 08 to `fabricctl` (phase 1). | 2026-09-27 | planned (phase 1) |
| S7 | Large multi-function files: `deploy.py` (~690 lines), `interactive.py` (~810), `manage.sh`, `certs.sh`, `services.sh`, `tsig.sh`, `vars.sh` | Predate the one-function-per-file rule. Not dead — structure debt. | — | Split by domain when touched (AGENTS.md §2); `fabricd` / `fabricctl` code is written in the new layout from the start. | 2026-09-27 | planned |
| S8 | `fabric/playbooks/*`, Ansible path in `setup.sh` | Whole Ansible installer, to be replaced by native `fabricctl setup` (design §4). Still the only installer today. | Current install path. | Keep until phase 2; then `setup.sh` becomes a thin wrapper for one release, then delete. | 2026-09-27 | planned (phase 2) |

## Removed (no value) — for the record

| Date | Removed | Why |
|---|---|---|
| 2026-09-27 | `fabric/jinja/nginx/www/manual/test.html` | Dev scratch page; unreferenced, never deployed. |
| 2026-09-27 | `fabric/jinja/nginx/www/manual/index.html` | Stale copy; the live page is rendered from `index.html.j2`. |
| 2026-09-27 | `IMPACT_MAP` / `map_service()` in `interactive.py` | Never called; superseded by change tracking in `deploy.py`. |
| 2026-09-27 | `enforce_ldaps` setting | Rendered but read by nothing; 389-DS always enforces secure binds. |
| 2026-09-27 | Unused `now` variable in `deploy.py` `unique_filter` | Dead assignment. |
| 2026-09-27 | `.version` handling in `setup.sh` uninstall | File not written for several releases; it also stopped local uninstalls from offering a snapshot (fixed: now checks for the install dir). |
| earlier | `__pycache__` / `*.pyc` in git | Generated files. |
