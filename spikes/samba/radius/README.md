# spikes/samba/radius

| File | What |
|---|---|
| `Dockerfile` | Debian's FreeRADIUS as uid/gid 610 with winbind's `ntlm_auth` and `eapol_test`; PEAP by default |
| `mschap` | MS-CHAPv2 checked by AD through `ntlm_auth` |
| `inner-rewrite` | A machine's `host/<name>.<domain>` becomes `<name>$` |
| `radius.sh` | Writes the client list (its secret from a file) on the `/run` tmpfs and starts FreeRADIUS |
