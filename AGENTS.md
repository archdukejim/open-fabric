# AGENTS.md — rules for building fabric

Guidance for anyone (human or AI agent) changing this repository. Read it
before writing code. Product design lives in
[docs/design/fabricctl-package.md](docs/design/fabricctl-package.md); this
file is about *how* we build.

## 1. What we are building

- **fabricctl** — the control. Native apt package on the host: `fabricctl`
  CLI + root `fabric-agent` daemon + systemd units (timers planned). Installs, configures,
  updates and secures the whole stack. Works fully without the web UI.
- **Open Fabric** (web control) — the control-plane web UI, its own unprivileged container.
  Every action is a request to `fabric-agent`; it holds no power of its own.
- One repo, two artifacts. Targets: **arm64 and amd64**; reference hardware
  is a **4 GB Raspberry Pi on Ubuntu Server 24.04**.

The repository has three product folders (design D25):

| Folder | What goes there |
|---|---|
| `fabricctl/` | Everything that runs on the Linux host: `fabriclib`, `fabric-agent`, the deploy engine, service templates, `images.lock.yaml`, `VERSION` |
| `webui/` | The control-plane container: its Python app and `Dockerfile`. It never imports `fabriclib` at runtime (the dev preview may, from a checkout) |
| `installers/<format>/` | Wrappers that package the two for a platform — today only `installers/deb/` |

The installed layout is assembled by `installers/deb/assemble-tree.sh` and
did not change with the split: never make a runtime path depend on the
repository layout.

## 2. Layout: one function per file, grouped by folder

The repo must stay easy to navigate. For all of our own code:

- **Every distinct function/operation lives in its own file**, named for what
  it does (`verb_noun`): `dns/add_record.py`, `pki/issue_client_cert.py`,
  `vault/add_kmip_slot.py`. A reader should find the code for an operation from
  its name alone.
- Small private helpers used by exactly one function stay in that function's
  file. A helper used by two or more files moves to its own file in that
  folder's `common/` (or the top-level `common/` if cross-domain) — still one
  helper per file.
- **Group files by domain in folders** (today: `dns/`, `dhcp/`, `pki/`, `ldap/`,
  `keycloak/`, `vault/`, `secrets/`, `images/`, `security/`, `setup/`,
  `radius/`, `logs/`, `rbac/`, `system/`, `consent/`, `undo/`, `common/`). Prefer a new folder over a crowded one.
- Python domain code lives in **`fabricctl/lib/fabriclib/<domain>/`** and is
  imported as `fabriclib.<domain>.<file>` — namespaced so it can never
  collide with system packages (e.g. dnspython is also `dns`).
- **Entry points only route.** CLI dispatchers (`fabricctl`), API routers
  (`fabric-agent`) and web handlers parse input and call one function file; no
  business logic in them.
- **Every folder has a `README.md`**: one line per file saying what it does.
  Update it in the same change that adds, renames or removes a file.
- Templates stay under `fabricctl/jinja/<service>/`; tests mirror the code
  layout under `tests/<domain>/`; docs under `docs/`, designs under
  `docs/design/`.
- The large files that predated this rule were split in 2026-10 (stale-code
  S7). The entry points that remain (`deploy.py`, `interactive.py`,
  `keycloak_bootstrap.py`, `manage.sh`, `agent/server.py`, the web UI's
  `server.py` and `devserver.py`) only route: keep it that way.

## 3. Stale code

- **No potential value → delete it in the same change** (dead functions,
  unused variables/settings, orphaned scratch files, duplicate copies).
  Say what was removed and why in the commit message.
- **Possibly useful but unused → do not delete.** Add it to
  [docs/maintenance/stale-code.md](docs/maintenance/stale-code.md) with path,
  what it is, why it is stale, its possible value and a recommendation. The
  owner decides later.
- Verify before calling code stale: search for callers across the repo
  (including templates, systemd units, tests and docs), not only the
  file's own language.
- Docs that describe things that no longer exist are stale too: fix them,
  or register them if the fix depends on a pending decision.

## 4. Security defaults (never weaken silently)

- Secure by default; every relaxation is an explicit setting, shown in
  `fabricctl status` and the Open Fabric web UI.
- Containers: non-root, `cap_drop: ALL` (+ only what is needed),
  `no-new-privileges`, read-only root where possible. Nothing mounts the
  Docker socket. Nobody is added to the `docker` group.
- Privileged work happens only in `fabric-agent`, through a fixed, validated API
  — never "run this command".
- Secrets never on a command line (`argv` is world-readable); pass them via
  files (0400/0600) or environment. No hard-coded or shared default
  passwords.
- TLS everywhere, verified against the fabric root CA — never
  `verify off` for new code.
- Images are pinned by digest from the signed channel; local builds start
  `FROM` a pinned digest. An upstream push must never change what runs.
- Core services (DNS, DHCP, LDAP, SSO, nginx) must never depend on OpenBao
  to *start*.

## 5. Must work

- On **arm64 and amd64**. Check every new image publishes both
  (`docker buildx imagetools inspect <image>`). Mind the memory budget at
  4 GB (see design §7a) and set a limit for every new container.
- **Offline.** Any feature that fetches something must have an offline path
  (bundle / local registry / local mirror).
- **Idempotent.** Every install, seed or configure step can be re-run safely
  and converges.
- **Upgrades from existing fabric installs** (re-running setup on a live
  host) — never only fresh installs. No compatibility code for pre-fabric
  (core-template) installs: those are rebuilt.

## 6. Testing

- Prove behaviour against **real containers**, not mocks, wherever a
  container is involved: `sudo tests/run-all.sh [suite …]`.
- Add or extend a suite in `tests/<domain>/` with every feature, including
  the negative/security cases (what must be refused).
- A change is not done until the relevant suites pass; report results
  faithfully, including what was not run.

## 7. Repo hygiene

- Work on the `fabric` branch; **never commit to `main`**.
- LF line endings everywhere (enforced by `.gitattributes`).
- No generated files in git (`__pycache__`, rendered output, test output).
- Commit messages explain *why*; end with the co-author line used in this
  repo.
- Keep docs in the same change as the code they describe.
