# tests/ntp

| File | What |
|---|---|
| `run.py` | Time with real chrony (fabric's pinned Debian image, never setting the clock): the settings and what they refuse, the upstream site first, what deploy_chrony writes (LAN only, own clock as last resort, -s/-x, chrony-wait limit, nothing changed when nothing is new); a served LAN client gets the time, another network gets no answer; a second site syncs from its upstream site; time_status and query_time against real chrony |
