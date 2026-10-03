# Handoff: aligning fabric to the global working rules (2026-10-03)

Temporary session handoff, not documentation. Delete it once the alignment work is scoped in the manual.

## 1. Where things stand

- **`main`** has everything up to PR #4 (merged by the owner 2026-10-03, merge commit `f2572c2`): fabricctl, the
  Open Fabric web UI, federation M1–M5 and M7–M9, the consent work, `setup --undo`, the dirsrv stale-pid fix.
  Last full test state before the merge: the sandbox passed 192/192; docs, render, dirsrv, keycloak, consent,
  webui, fluentbit and hardening passed (one hardening run had step-ca exit right after start; it passed on
  re-run).
- **`feature/manual-alignment`** (this branch, from `main`): created for aligning the repo to the owner's global
  rules. Nothing changed yet except this file.
- **`feature/federation`** and **`fabric`** are fully merged into `main`.
- **Samba**: design written, `docs/design/samba-ad.md` (S0–S8 plan, 6 open decisions S1–S6 in §11). The owner
  said: after the merge make a branch `samba` and begin — **paused** by the owner for the rules rework. Under
  global Rule 4 the open decisions must be answered (or a spike rule added, see R8) before S0 starts.
- The GitHub repo moved to `archdukejim/open-fabric`; pushes work through the redirect. The local remote still
  points at the old name (`git remote set-url origin git@github.com:archdukejim/open-fabric.git`, not yet done:
  owner not asked yet).

## 2. The global rules

`~/.claude/CLAUDE.md` (copy at `~/.codex/AGENTS.md`), last changed 2026-10-03 14:16: Rules 1–7 — code layout
(scope: code/scripts only, not templates/markup/styles/config), build from a design document, scope before work,
design complete before coding, the 5-volume manual under `docs/` (numbering V.C.S.T, never reuse numbers,
5.8 topics spanning volumes), manual compilation on request only, repository layout (Rule 7: `src/`, `tests/`,
`scripts/`, `packaging/`, `templates/`, `static/`, `config/`; root holds only README, LICENSE,
THIRD_PARTY_NOTICES, required tool config; variants rules 7.2). Backups beside it (`CLAUDE.md.bak-*`).

## 3. Owner decisions already made for the alignment

| # | Question | Answer |
|---|---|---|
| A1 | AGENTS.md | Everything goes in the manual; the local agent file only points to the manual for scope |
| A2 | Generated function reference (`docs/lib-doc/`, ~10k lines) | A generated appendix in Volume 1 |
| A3 | Old IDs (D1–D25, M1–M10, F1–F8, J1–J3, S0–S8) | Kept as labels in topic titles; V.C.S.T is canonical |
| A4 | Files over ~300 lines | Split the test scripts (9 files, up to 633 lines); templates/stylesheets/config/vendored exempt |

## 4. Open questions for the owner (asked, not answered)

1. Edit the global CLAUDE.md with the rule gaps below, or will the owner rework it first? (The owner said they
   will rework it; the new agent should read the current file before anything else.)
2. Is fabric **one project** (`src/` holding host code and the web UI, which ships inside the one .deb — proposed)
   or two deployed parts under `services/fabricctl/` and `services/webui/`?
3. Rule 7's repo restructure: in this branch with the manual, or its own branch after the manual?
4. Promote the general decisions in §6 into the global rules? Proposed: yes, as new numbered rules.

## 5. Gaps in the rules themselves (proposed wording, R1–R16)

- R1 Agent files: `AGENTS.md`/`CLAUDE.md` at the root only as pointers to `docs/README.md` (≤ 20 lines, no rules);
  7.1's root list should name them.
- R2 Generated docs: exempt from 5.7 renumbering, never hand-edited; numbers from a committed registry so they stay
  stable.
- R3 Legacy IDs allowed as labels; V.C.S.T canonical.
- R4 Vendored/minified/third-party code outside Rule 1, under `static/vendor/` or `src/vendor/` with version,
  source URL and checksum, listed in THIRD_PARTY_NOTICES.
- R5 Tests follow Rule 1 (one file per unit/scenario, mirroring `src/`); system tests across units in
  `tests/system/`.
- R6 Product templates vs build packaging: files the product renders or builds at runtime (compose, the
  Dockerfiles it deploys) are templates; `packaging/` only builds the repo's release artifacts.
- R7 CPU architectures are build-matrix entries, not variants; every image publishes every supported architecture.
- R8 Spikes allowed before the design is complete only when scoped in the manual as a design task, no product
  code, findings recorded in Volume 5.
- R9 5.5 needs the owner's explicit yes, not only presenting; precedence: global rules, then the project manual
  (stricter allowed, never looser); on conflict ask.
- R10 Agent memory holds only working preferences and pointers; project facts and decisions go in the manual.
- R11 A bug fix restoring documented behaviour cites its chapter; one that changes behaviour updates the manual
  first.
- R12 An unrelated request (Rule 3) is designed in its own chapter, on its own branch, after the owner decides.
- R13 Git workflow, commit rules, testing and review live in Volume 4; security defaults' home chapter in Volume 1.
- R14 Chapters are folders, subchapters files, named with their number prefix (`1.2-federation/1.2.3-joining.md`).
- R15 Open decisions tracked in a numbered Volume 5 chapter with status until answered.
- R16 Folder READMEs indexing files are allowed as summaries, with no design content.

## 6. Decisions the owner made in this project that the global rules do not cover

General (candidates for new global rules):

1. Ask before any change outside the app's own tree (system files, firewall, accounts, other apps' config):
   grouped questions up front, an explicit flag for unattended runs, no default answer.
2. Integrations with other software go in separate bridge packages with their own lifecycle; fail loudly.
3. Uninstall lists what it undoes and restores the system as it was; undo on request.
4. No extra package sources: the OS's own archive.
5. Prefer long-term-supported components; avoid complicated upgrades.
6. Pin images by digest; build locally from a pinned base when upstream is stale.
7. Prefer an existing community tool over building one.
8. Secure by default; every relaxation an explicit setting shown in status and the UI.
9. Secrets never on argv or in git; 0600 files or environment; no shared default passwords.
10. TLS verified everywhere; least privilege (non-root, no capabilities, no Docker socket).
11. Dev/preview modes can never be enabled in production.
12. Offline path for anything that downloads.
13. Idempotent installs and steps.
14. Upgrades from existing installs work, not only fresh ones; no compatibility code for what will be rebuilt.
15. Every supported CPU architecture; a memory limit for every container (the 4 GB Pi budget).
16. Test against real components, not mocks, including refusal/security cases.
17. Done only when its suites pass; report results faithfully, including what was not run.
18. Ask before changing a test host's system; never disturb the owner's other environments.
19. Entry points only route (no business logic in CLI dispatchers, API routers, web handlers).
20. Stale code: delete when it has no value, register when it might; check callers everywhere first.
21. Structured docstrings on every function (purpose, inputs, returns, failures, callers) and a generated reference.
22. Never commit to `main`; feature branches; push after commits.
23. Commit messages say why; end with the co-author line.
24. Docs in the same change as the code.
25. LF line endings everywhere.
26. Merge to `main` only when stable (all suites and CI green), and the owner merges — the agent never merges or
    auto-merges (the agent's merge attempt was blocked by its permission guard on 2026-10-03; the owner merged).
27. Order work by what can be tested now; defer what needs unavailable hardware (multi-site until host-1/host-2
    are rebuilt).

Fabric-only (go in this repo's manual during the alignment): the `fabric-*` accounts in uid band 600–649; purge
keeps downloaded images; the installed layout never depends on the repo layout; D1–D25 and the M/F/J/S
decisions; the owner's home network layout and the deferral of domain join, M6, the M5 cross-site gaps, F3, F4
and HA until after Samba (today in the agent's memory, which R10/5.2 do not allow); the WSL testing notes
(Volume 5 troubleshooting).

## 7. Repo gaps against the global rules (found, nothing changed)

- **Rule 5 (manual):** `docs/` is 51 flat files (~18k lines): `install`, `operations`, `vars`, `webui`,
  `architecture`, `keycloak`, `subordinate`, `disk-encryption`, `testplan`, `design/` (9 designs),
  `lib-doc/` (generated), `maintenance/` (stale code, review findings, review ledger). No volumes, no V.C.S.T.
- **Proposed mapping:** V1 — architecture, product design D1–D25, federation, web UI security model and RBAC, the
  agent API, Keycloak, code-layout and security rules, the generated function reference (appendix); V2 — settings
  (`vars`), DHCP, DNS filter, NTP, image updates, host consent, domain join, Samba AD, disk encryption; V3 —
  operations, the web UI tabs, the manual test plan; V4 — install/upgrade/uninstall, subordinate CA, builds and
  packaging, the test suites, git rules; V5 — stale code, review findings, decision tables and trade-offs,
  troubleshooting, open decisions.
- **Impact (presented to the owner, Rule 5.5):** no product design change; breaking for the in-browser manual
  (nginx serves `docs/` at `/manual/` with tabs hardcoded in `fabricctl/jinja/nginx/www/manual/index.html.j2` —
  make it read `docs/README.md`), ~187 references to doc files in 106 code/test files (e.g. "host-consent.md §4"),
  the docs tools in `tests/docs/` (links, READMEs, vars, CLI, API checks, `gen_lib_doc.py`,
  `review_ledger.py`), and packaging that ships `docs/` (`installers/deb/assemble-tree.sh`). Scope creep risk
  medium: keep it to moves, numbering and link updates, each step checked by `tests/run-all.sh docs`.
- **Rule 7 (layout):** today `fabricctl/` (lib, jinja templates, VERSION, images.lock.yaml), `webui/`,
  `installers/deb/`, `tests/`, root `AGENTS.md` and `CLAUDE.md`. Needs `src/`, `templates/`, `static/`, `config/`,
  `packaging/`, `scripts/`; THIRD_PARTY_NOTICES is missing (vendored marked and mermaid in
  `fabricctl/jinja/nginx/www/manual/` have no recorded source or checksum); the root README must be ≤ 1000 words
  with no design content (not checked yet).
- **Rule 1:** product code already fits (AGENTS.md's one-function-per-file is stricter). Test scripts over 300
  lines to split (decision A4): `tests/openbao/run.py` 633, `tests/webui/test_container.py` 604,
  `tests/sandbox/run.sh` 595, `tests/freeradius/run.py` 445, `tests/render.py` 438, `tests/sandbox/login_test.py`
  365, `tests/federation/run.py` 356, `tests/pki/run.py` 314, `tests/kea/run.py` 313.

## 8. Suggested next steps for the new agent

1. Read the owner's current `~/.claude/CLAUDE.md` (it is being reworked) and re-check §3–§7 against it.
2. Get answers to §4.
3. Per Rules 2–5: first write the alignment's own scope as a manual chapter (create `docs/README.md` and the five
   volume indexes, plus a Volume 5 chapter holding this plan and the open decisions), get the owner's yes, then
   move one volume per commit, fix references and tools, then the in-browser manual, then AGENTS.md/CLAUDE.md to
   a pointer, then Rule 7's layout (if in this branch), then the test splits.
4. Move the fabric decisions out of the agent memory into the manual (R10), then trim the memory.
5. After the alignment: the `samba` branch from `main`, starting with the Samba decisions S1–S6.

## 9. Working notes for the agent

- Tests run in WSL `Ubuntu-24.04` (real Docker): `MSYS_NO_PATHCONV=1 wsl -d Ubuntu-24.04 -- bash /mnt/c/.../script.sh`,
  always from a script file; keep a background keepalive (`exec -a fabric-keepalive sleep 14400`) during runs;
  never two `tests/run-all.sh` with the same `FABRIC_TEST_OUT`; dirsrv, keycloak and hardening need `render` in
  the same run. The owner's containers (nginx-proxy-manager, paperless `records-*`) run there too: ask before
  restarting Docker or WSL. If processes hang in state D on `super_lock`, only `wsl --shutdown` helps (ask first).
- The test Pi (`tempuser@192.168.4.57`, key in WSL) and the Windows lab hosts: see the agent memory; never enter
  passwords, never enable `install_kea` there (live LAN).
- Python edits from Git Bash: set `PYTHONUTF8=1` (the default code page is cp1252 and corrupts UTF-8).
