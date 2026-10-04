# spikes/samba/dc

| File | What |
|---|---|
| `Dockerfile` | Debian's `samba-ad-dc` on fabric's pinned Debian base, a `bind` group with gid 600 |
| `entrypoint.sh` | Provisions the domain once (BIND9_DLZ, RFC 2307), sets the administrator's password, runs the DC in the foreground |
| `setpass.py` | Sets a domain user's password from a file through Samba's Python bindings |
