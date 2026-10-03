# docs

| File | What |
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
| [`lib-doc/`](lib-doc/README.md) | Function reference, generated from the code's docstrings (`python3 tests/docs/gen_lib_doc.py`): every function's purpose, inputs, results, failures, what feeds on it and who calls it |
| [design/](design/) | Designs and decisions: `fabricctl-package.md` (D1–D25), `image-updates.md` (D21) |
| [maintenance/](maintenance/) | `stale-code.md`: code kept for later, and what was removed |
