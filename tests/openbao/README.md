# tests/openbao

| File | What |
|---|---|
| `run.py` | OpenBao from fabric's own templates on the real pinned image: vault key and unlock methods (key file, USB stick on a loop device, security key on SoftHSM2, HSM on a PyKMIP server), rotation, tampering, the kill switch, fabric's secrets, hardening — including what must be refused |

Needs Docker, root, `losetup`, `softhsm2` + `python3-pykcs11` (security keys)
and `python3-pykmip` (HSM): `sudo apt install softhsm2 python3-pykcs11 python3-pykmip`.
