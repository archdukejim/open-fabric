# tests/openbao

| File | What |
|---|---|
| `run.py` | OpenBao from fabric's own templates on the real pinned image: vault key and unlock methods (key file, USB stick on a loop device, security key on SoftHSM2), rotation, tampering, the kill switch, fabric's secrets, hardening — including what must be refused |

Needs Docker, root, `losetup`, and `softhsm2` + `python3-pykcs11` for the
security-key part (`sudo apt install softhsm2 python3-pykcs11`).
