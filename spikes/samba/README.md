# spikes/samba — the S0 spike (throwaway)

Answers the questions of manual 5.8.1.5 (Samba AD replacing 389-DS) with real containers. Never merged into
`src/` (global Rule 4); results are recorded in the manual (5.8.1.7).

Run in a Linux/WSL shell with Docker, from the repository root. Everything is named `s0-*` (containers, the
network `s0net`, images `s0/*`) and kept in `/var/tmp/s0`; nothing else is touched.

| File | What |
|---|---|
| `common.sh` | Shared setup: passwords in 0600 files, credentials files, the hardened DC and BIND, a client container, clean-up |
| `dc/` | The DC image: Debian's `samba-ad-dc` on fabric's pinned Debian base; provisions once, sets the administrator's password from a file |
| `bind/` | fabric's BIND (9.20, uid 600) plus Samba's DLZ module, serving the AD zone from the DC's database |
| `q1-q2.sh` | Q1 (a hardened DC, minimum capabilities, re-run) and Q2 (BIND with DLZ: answers, signed updates, refusals) |
| `q4.sh` | Q4 (per-site delegation on an OU) and Q5 (child domains) |
| `fabric-schema.py` | fabric's directory schema as AD schema objects (OIDs AD accepts, from fabric's UUID) |
| `q7.sh` | Q7 (Keycloak with AD as its user store: sign-in, refusals, a password reset landing in AD) |
| `radius/` | Debian's FreeRADIUS (uid 610) with `ntlm_auth` and `eapol_test`: PEAP-MSCHAPv2 checked by AD through the DC's winbind |
| `q8.sh` | Q8 (PEAP for a person and a machine, refusals) |
| `q3-q6.sh` | Q3 (fabric's schema, a device and a network in AD) and Q6 (an RODC: replication, cached sign-in with the root DC down, refusals) |

```bash
sudo bash spikes/samba/q1-q2.sh
```

```bash
sudo bash spikes/samba/q4.sh
```

```bash
sudo bash spikes/samba/q3-q6.sh
```

```bash
sudo bash spikes/samba/q7.sh
```

```bash
sudo bash spikes/samba/q8.sh
```

Keep the WSL distribution running for the whole run (a background `sleep`): if it idles out, Docker restarts
and every container stops.
