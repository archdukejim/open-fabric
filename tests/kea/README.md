# tests/kea

| File | What |
|---|---|
| `run.py` | Kea 3.0 built from fabric's Dockerfile (a wrong signing-key fingerprint refused) and rendered from fabric's templates, with BIND: busybox DHCP clients get pool addresses and reservations, their hostnames are registered in `dhcp.<domain>`, a second client cannot take a registered name, leases listed over the control socket, a restart over the previous run folder (stale PID file), the DDNS key refused outside its zone, container hardening |
