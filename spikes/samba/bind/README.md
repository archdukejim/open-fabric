# spikes/samba/bind

| File | What |
|---|---|
| `Dockerfile` | fabric's BIND (Debian, 9.20, uid 600) plus `samba-libs` and `samba-dsdb-modules` for the DLZ module |
| `dlz.sh` | Points BIND at the DLZ module of this architecture and runs it |
| `named.conf` | fabric's zone as usual and the AD zone through DLZ; the DC's DNS key for signed updates |
| `db.lan.test` | A stand-in for fabric's own zone |
