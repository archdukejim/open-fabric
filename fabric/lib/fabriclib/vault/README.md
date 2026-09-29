# fabriclib/vault

OpenBao (secrets), a core fabric service. The host talks to its API over
fabric_net with TLS verified against the fabric root CA; after the first
init it authenticates only with fabric's own AppRoles (the root token is
revoked).

| File | What |
|---|---|
| `constants.py` | Key/credential file names, KV mounts, the fabric-setup and fabric-agent policies |
| `ensure_unseal_key.py` | The static-seal key: 32 bytes, 0400, openbao user only; never replaced, never regenerated next to existing data |
| `init_openbao.py` | Initialise once: recovery keys + initial root token (None if already initialised) |
| `configure_openbao.py` | Converge: AppRole auth, KV v2 `fabric/` + `apps/`, policies, AppRoles bound to fabric_net, their credentials (root 0400) |
| `revoke_token.py` | Revoke a token (the initial root token after bootstrap) and confirm it is dead |
| `vault_status.py` | Reachable, initialised, sealed, version, seal/storage type, seal-key file state, engines and auth methods (as fabric-agent); no secrets |
| `list_slots.py` | Unlock methods (key slots) with type, device, presence and key version — today the local key file |
| `detect_devices.py` | Security keys (by USB vendor + serial) and USB disks (model, serial, UUID) plugged into the host, read-only |
| `run_vault_command.py` | `fabricctl vault status` |
| `common/` | Helpers shared by the operations above (see its README) |
