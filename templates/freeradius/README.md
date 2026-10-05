# jinja/freeradius

Optional 802.1X (design §6). FreeRADIUS 3.2 from Debian's packages; every
decision is fabric's policy, which asks the site's domain controller (AD) about the device.

| File | What |
|---|---|
| `docker-compose.yml.j2` | The `freeradius` container: uid 916, no capabilities, read-only, UDP 1812/1813 on the host IP, on fabric_net |
| [`packaging/images/freeradius/`](../../packaging/images/freeradius/) | The image: Debian's freeradius + python3 module + python3-ldap on the pinned Debian base; fabric's uid/gid |
| `config/radiusd.conf.j2` | Main configuration: fabric's own minimal tree, logs to the journal (decisions, never passwords) |
| `config/clients.conf.j2` | RADIUS clients (switches, APs) with their secrets from OpenBao; Message-Authenticator required unless relaxed |
| `config/fabric-radius.json.j2` | Where the policy finds the DC (LDAPS to the host's address, verified), its read-only account `fabric-radius-<site>`, and the groups mapped for password logins |
| `config/mods/always.j2` | `ok` (accounting is acknowledged, not stored) |
| `config/mods/eap.j2` | EAP-TLS (fabric CA only, no session resumption; the verify step that records each certificate's fingerprint); EAP-TTLS only while a group is mapped; no PEAP/MSCHAPv2 |
| `config/mods/fabric_policy.j2` | The python3 module that runs `python/fabric_radius.py` |
| `config/sites/fabric.j2` | The server switches talk to: EAP, or MAB for everything else |
| `config/sites/inner-tunnel.j2` | Inside EAP-TTLS: a person's user name and password, decided by the policy |
| `config/sites/check-eap-tls.j2` | Runs the policy once a client certificate chained to the fabric CA; its VLAN goes into the Access-Accept |
| [`src/containers/freeradius/`](../../src/containers/freeradius/) | fabric's policy code (the python3 module's scripts, installed as `python/`): EAP-TLS by linked certificate, MAB by MAC, people by password; listed in that folder's README |

Rendered and copied to `<deploy_base>/freeradius/` by `fabriclib/radius/deploy_freeradius.py`
(config and python root:freerad 0640); tested by `tests/freeradius/run.py`.
