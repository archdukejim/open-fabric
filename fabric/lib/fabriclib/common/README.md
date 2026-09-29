# fabriclib/common

| File | What |
|---|---|
| `paths.py` | Well-known paths derived from the install location (`FABRIC_DIR`, `VARS_FILE`, `AUDIT_FILE`, …) |
| `read_images_lock.py` | The validated, digest-pinned images (`fabric/images.lock.yaml`) with their refs |
| `errors.py` | `ValidationError` — input rejected; message is safe to show to users |
| `load_vars.py` | Read `vars.yaml` (empty dict if missing) |
| `save_vars.py` | Write `vars.yaml`, empty strings stored as null |
| `vars_lock.py` | Exclusive lock around read-modify-write of `vars.yaml` |
| `write_audit.py` | Append one line to the audit log with the acting user and source |
| `read_audit.py` | Last N audit lines, newest first |
| `run.py` | Run a command as an argument list (never a shell); raise `CommandError` with stderr on failure |
| `console.py` | `heading` / `info` / `ok` / `warn` / `err` output (colour only on a terminal) |
| `wait_healthy.py` | Wait for a container's Docker healthcheck |
| `dns_query.py` | A-record lookup against one DNS server (stdlib; no `dig` needed) |
| `sudo_owner.py` | Login, home, uid and gid of the account that ran `sudo` (files handed to the admin) |
| `set_tsig_secrets.py` | Set or remove TSIG secrets in `fabric-secrets.yml` (kept `0600`) |
