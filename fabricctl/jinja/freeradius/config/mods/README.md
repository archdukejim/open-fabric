# jinja/freeradius/config/mods

Rendered to `/opt/freeradius/config/mods/<name>` by
`fabriclib/radius/deploy_freeradius.py`.

| File | What |
|---|---|
| `always.j2` | The `ok` module (accounting is acknowledged, not stored) → `always` |
| `eap.j2` | EAP-TLS (fabric CA only, no session resumption; its verify step runs `python/record_fingerprint.py`); EAP-TTLS only while a group is mapped; no PEAP/MSCHAPv2 → `eap` |
| `fabric_policy.j2` | The python3 module that loads `python/fabric_radius.py` (instantiate, authorize) → `fabric_policy` |
