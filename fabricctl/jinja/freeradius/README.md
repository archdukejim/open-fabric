# jinja/freeradius

Optional 802.1X (design §6). FreeRADIUS 3.2 from Debian's packages; every
decision is fabric's policy, which asks 389-DS about the device.

| File | What |
|---|---|
| `docker-compose.yml.j2` | The `freeradius` container: uid 916, no capabilities, read-only, UDP 1812/1813 on the host IP, on fabric_net |
| `build/Dockerfile` | The image: Debian's freeradius + python3 module + python3-ldap on the pinned Debian base; fabric's uid/gid |
| `config/radiusd.conf.j2` | Main configuration: fabric's own minimal tree, logs to the journal (decisions, never passwords) |
| `config/clients.conf.j2` | RADIUS clients (switches, APs) with their secrets from OpenBao; Message-Authenticator required unless relaxed |
| `config/fabric-radius.json.j2` | Where the policy finds 389-DS (LDAPS, verified), its read-only account `cn=radius_reader`, and the groups mapped for password logins |
| `config/mods/always.j2` | `ok` (accounting is acknowledged, not stored) |
| `config/mods/eap.j2` | EAP-TLS (fabric CA only, no session resumption; the verify step that records each certificate's fingerprint); EAP-TTLS only while a group is mapped; no PEAP/MSCHAPv2 |
| `config/mods/fabric_policy.j2` | The python3 module that runs `python/fabric_radius.py` |
| `config/sites/fabric.j2` | The server switches talk to: EAP, or MAB for everything else |
| `config/sites/inner-tunnel.j2` | Inside EAP-TTLS: a person's user name and password, decided by the policy |
| `config/sites/check-eap-tls.j2` | Runs the policy once a client certificate chained to the fabric CA; its VLAN goes into the Access-Accept |
| `python/fabric_radius.py` | The policy: EAP-TLS by linked certificate (`network:eap-tls`), MAB by MAC (`network:mab`), people by password (mapped groups); the VLAN; fail closed; one `fabric:` log line per decision |
| `python/lookup_device.py` | Find a device by certificate fingerprint or MAC in 389-DS and judge it (enabled, permission, VLAN by role priority) |
| `python/check_person.py` | Check a person's password by binding as them (lockout applies) and their mapped groups (VLAN by priority) |
| `python/directory.py` | The policy's LDAPS connection to 389-DS: the reader account per thread, or a bind as a person |
| `python/record_fingerprint.py` | EAP-TLS verify command: SHA-256 fingerprint of the presented certificate, keyed by its serial |
| `python/normalize_mac.py` | Any MAC spelling → `aa:bb:cc:dd:ee:ff` |

Rendered and copied to `<deploy_base>/freeradius/` by `fabriclib/radius/deploy_freeradius.py`
(config and python root:freerad 0640); tested by `tests/freeradius/run.py`.
