# fabriclib/vault/common

| File | What |
|---|---|
| `bao_request.py` | One OpenBao API call on its fabric_net address, TLS verified for its host name (or over the root-only break-glass socket) |
| `approle_login.py` | Log in with a stored AppRole (role_id + secret_id file, root 0400) → short-lived token |
| `write_private_file.py` | Atomically write a file that is never readable by anyone but its owner |
| `read_slot_store.py` | The unlock-method store (`slots.json`), or None |
| `write_slot_store.py` | Save it root-only, signed with the vault key |
| `slot_store_mac.py` | The store's signature (HMAC with the vault key) |
| `key_check_value.py` | Proof that an unwrapped key is the vault key, revealing nothing about it |
| `obtain_key.py` | Try the methods for a key version; first verified one wins; a broken device never blocks the others |
| `slot_type.py` | The `slots/<type>.py` module for a type name |
| `kmip_session.py` | A KMIP client on a TLS connection fabric makes itself (server certificate verified; PyKMIP's own TLS does not verify it) |
| `pkcs11_modules.py` | The PKCS#11 libraries fabric may load (allowed list from `openbao_pkcs11_modules`; they run as root) |
| `load_pkcs11.py` | Load one library with PyKCS11 (clear error if python3-pykcs11 is missing) |
| `find_token.py` | The token with a given serial in a library, or None (no login) |
| `pkcs11_session.py` | Logged-in session that never spends a last PIN try, and does not retry unattended after a wrong PIN |
| `wait_active.py` | Wait until OpenBao is the active node (unsealed is not enough right after a start) |
| `write_seal_config.py` | `seal.hcl`: which key id(s) OpenBao's static seal reads from RAM |
