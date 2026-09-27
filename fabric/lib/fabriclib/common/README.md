# fabriclib/common

| File | What |
|---|---|
| `paths.py` | Well-known paths derived from the install location (`FABRIC_DIR`, `VARS_FILE`, `AUDIT_FILE`, …) |
| `errors.py` | `ValidationError` — input rejected; message is safe to show to users |
| `load_vars.py` | Read `vars.yaml` (empty dict if missing) |
| `save_vars.py` | Write `vars.yaml`, empty strings stored as null |
| `vars_lock.py` | Exclusive lock around read-modify-write of `vars.yaml` |
| `write_audit.py` | Append one line to the audit log with the acting user and source |
| `read_audit.py` | Last N audit lines, newest first |
