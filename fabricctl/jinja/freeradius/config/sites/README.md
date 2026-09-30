# jinja/freeradius/config/sites

Rendered to `/opt/freeradius/config/sites/<name>` by
`fabriclib/radius/deploy_freeradius.py`.

| File | What |
|---|---|
| `fabric.j2` | The server switches talk to: EAP, or MAB (the policy by MAC) for everything else → `fabric` |
| `check-eap-tls.j2` | Runs the policy once a client certificate chained to the fabric CA; its VLAN goes into the Access-Accept → `check-eap-tls` |
| `inner-tunnel.j2` | Inside EAP-TTLS: marks the request `Tmp-String-0 = fabric-people` and lets the policy check the person's user name and password → `inner-tunnel` |
