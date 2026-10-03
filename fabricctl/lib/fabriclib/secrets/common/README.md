# fabriclib/secrets/common

OpenBao access to the `fabric/secrets` KV v2 entry, logged in with the
setup AppRole (`setup-approle.json`) unless a token is given.

| File | What |
|---|---|
| `read_vault_secrets.py` | The entry and its version (`({}, 0)` if absent); unreachable or sealed OpenBao is an error |
| `write_vault_secrets.py` | A new version, check-and-set against the version read (concurrent changes refused) |
