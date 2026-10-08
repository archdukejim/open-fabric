# packaging/images/samba

fabric's Samba AD domain controller (manual 1.6.5): Debian's `samba-ad-dc` on the validated Debian base.

| File | What |
|---|---|
| `Dockerfile` | The image: Samba's DC packages, `nsupdate` (the DC registers its names in BIND, signed); BIND's and FreeRADIUS's groups baked in (`org.fabric.groups`) |
| `entrypoint.sh` | Provisions the domain once (or joins it as a DC or RODC), converges fabric's `smb.conf` options, runs the DC |
| `set_password.py` | Sets an account's password from a file through Samba's Python bindings |
