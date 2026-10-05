# tests/samba

The `samba` suite (manual 2.11.2.13): the Windows domain controller.

| File | What |
|---|---|
| `run.py` | Settings (D87, D89), the Administrator's password, the rendered container's hardening, nginx giving up 389/636, the unit |
| `dc.py` | Real containers: a DC from fabric's image run as rendered, deployed and converged by fabric's code (twice: idempotent), the policy and GPOs in place; BIND (fabric's image, sharing the DC's address as on a host) answering the AD zone through DLZ and fabric's zone unchanged, the DC's signed updates accepted; an RODC joining with fabric's image (NTLM forwarded for accounts it does not cache; with the writable DC down, cached people only, no writes); refusals: unsigned updates in either zone, a site admin in another site or its service accounts, a short or wrong password |
| `start_dc.py` | A converged DC for any suite that needs AD (tests/keycloak): fabric's image, hardening, deploy and convergence, a test PKI |
