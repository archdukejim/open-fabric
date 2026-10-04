# jinja/freeradius/python

fabric's 802.1X policy, run inside the `freeradius` container. Copied (not
rendered) by `fabriclib/radius/deploy_freeradius.py` to
`/opt/freeradius/python/` (root:freerad 0640), mounted read-only at
`/etc/freeradius/python`. Tested by `tests/freeradius/run.py`.

| File | What |
|---|---|
| `fabric_radius.py` | The policy module (`mods/fabric_policy`): EAP-TLS by linked certificate, MAB by MAC, people by password; the VLAN; fail closed; one `fabric:` log line per decision |
| `lookup_device.py` | Find a device by certificate fingerprint or MAC in 389-DS and judge it (enabled, permission, VLAN by role priority) |
| `check_person.py` | Check a person's password by binding as them (lockout applies) and their mapped groups (VLAN by priority) |
| `directory.py` | The policy's LDAPS connection to 389-DS: the reader account per thread, or a bind as a person |
| `record_fingerprint.py` | EAP-TLS verify command: SHA-256 fingerprint of the presented certificate, stored under its serial in `/run/freeradius/fp` |
| `normalize_mac.py` | Any MAC spelling → `aa:bb:cc:dd:ee:ff` |
