# fabriclib/vault/slots

One file per unlock-method (key slot) type, picked by name through
`common/slot_type.py`. Each exposes `wrap(v, slot, key, key_id)` → record
(`pkcs11` and `kmip` also take `attended`), `unwrap(v, slot, record,
attended=False)` → key or None (the caller verifies it against the check
value), `present(v, slot)`, `forget(v, slot, record)` (destroy one key
version's copy), optionally `discard(v, slot)` (the whole method is removed),
and `TESTED` (what it was tested against; "untested" parts say so).

| File | Type | Tested against |
|---|---|---|
| `local.py` | key file on this host (root, 0400) | real OpenBao image |
| `pkcs11.py` | vault key RSA-OAEP-wrapped by a non-extractable RSA key on a PKCS#11 token; PIN root 0400 on the host (`pin-<id>`); `discard` deletes it | SoftHSM2 (generate, existing key, wrap/unwrap, PIN guard, rotate, remove); **YubiKey / Nitrokey / smart cards untested** |
| `kmip.py` | vault key AES-256-CBC-encrypted by a key inside an HSM / key manager (any KMIP server), mutual TLS verified against the given CA; its certificates root 0400 in `kmip-<id>/`; `discard` deletes them | PyKMIP server (wrap/unwrap, wrong CA refused, rotate, revoke = kill switch); **vendor HSMs untested** |
| `usb.py` | key file on a stick fabric formats (ext4, label FABRIC-KEY, fabric-chosen UUID, root 0400); identified by UUID + serial | loop device (format, read, rotate, remove); real stick on a Pi 5 (arm64): add, unlock from it alone, pull → stopped, re-plug → unsealed |
