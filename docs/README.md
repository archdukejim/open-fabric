# fabric manual

The manual is fabric's only source of truth: architecture, decisions, procedures and notes (global Rule 5).

## [Volume 1 — Systems and services](volume_1_systems_and_services/README.md)

- 1.2 Decision register

## [Volume 2 — Technologies and features](volume_2_technologies_and_features/README.md)

## [Volume 3 — Operations](volume_3_operations/README.md)

## [Volume 4 — Infrequent operations](volume_4_infrequent_ops/README.md)

## [Volume 5 — Notes and troubleshooting](volume_5_notes_and_troubleshooting/README.md)

- 5.1 Manual alignment
- 5.5 Reasoning and trade-offs

---

**Temporary, until the alignment is done (5.1.1):** documents written before the manual, still to move into it.
This list is removed when they have moved.

| Document | What |
|---|---|
| `install.md` | Install, upgrade, reinstall, uninstall / export / restore |
| `operations.md` | Day-2: `fabricctl` commands, OpenBao and its unlock methods, secrets, images, log forwarding |
| `webui.md` | Open Fabric — web control: tabs, security model, who may do what (RBAC), first sign-in |
| `vars.md` | Every setting in `vars.yaml` |
| `architecture.md` | How the pieces fit: containers, networks, files, units |
| `keycloak.md` | Keycloak and the directory behind it |
| `subordinate.md` | Using an existing CA (subordinate Step-CA) |
| `disk-encryption.md` | Manual: LUKS for fabric's data, unlocked by the same YubiKey or USB stick |
| `testplan.md` | Manual test plan (and which parts are automated) |
| [`lib-doc/`](lib-doc/README.md) | Function reference, generated from the code's docstrings (`python3 tests/docs/gen_lib_doc.py`) |
| [design/](design/) | Designs: `fabricctl-package.md` (D1–D25 now in 1.2.1), `federation.md`, `image-updates.md` and the feature designs |
| [maintenance/](maintenance/) | `stale-code.md`: code kept for later, and what was removed |
