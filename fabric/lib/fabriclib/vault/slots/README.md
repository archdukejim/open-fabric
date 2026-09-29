# fabriclib/vault/slots

One file per unlock-method (key slot) type. Each exposes `wrap(v, slot, key,
key_id)` → record, `unwrap(v, slot, record)` → key or None, `present(v,
slot)`, `forget(v, slot, record)`, optionally `discard(v, slot)` (the whole method is removed), and `TESTED` (what it was tested against;
"untested" parts say so).

| File | Type | Tested against |
|---|---|---|
| `local.py` | key file on this host (root, 0400) | real OpenBao image |
| `pkcs11.py` | vault key RSA-OAEP-wrapped by a non-extractable RSA key on a PKCS#11 token; PIN root 0400 on the host (`pin-<id>`); `discard` deletes it | SoftHSM2 (generate, existing key, wrap/unwrap, PIN guard, rotate, remove); **YubiKey / Nitrokey / smart cards untested** |
| `usb.py` | key file on a stick fabric formats (ext4, label FABRIC-KEY, fabric-chosen UUID, root 0400); identified by UUID + serial | loop device (format, read, rotate, remove); real stick on a Pi 5 (arm64): add, unlock from it alone, pull → stopped, re-plug → unsealed |
