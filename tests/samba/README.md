# tests/samba

The `samba` suite (manual 2.11.2.13): the Windows domain controller.

| File | What |
|---|---|
| `run.py` | Settings (D87, D89), the Administrator's password, the rendered container's hardening, nginx giving up 389/636, the unit |
| `dc.py` | Real containers: a DC from fabric's image run as rendered, deployed and converged by fabric's code (twice: idempotent), the policy and GPOs in place; BIND (fabric's image, sharing the DC's address as on a host) answering the AD zone through DLZ and fabric's zone unchanged, the DC's signed updates accepted; refusals: unsigned updates in either zone, a site admin in another site or its service accounts, a short or wrong password |
