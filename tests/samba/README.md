# tests/samba

The `samba` suite (manual 2.11.2.13): the Windows domain controller.

| File | What |
|---|---|
| `run.py` | Settings (D87, D89), the Administrator's password, the rendered container's hardening, nginx giving up 389/636, the unit |
| `dc.py` | Real containers: a DC from fabric's image run as rendered, deployed and converged by fabric's code (twice: idempotent), the policy and GPOs in place; the address plan (each site's networks converged into AD, read across two sites, an overlap found, a removed network leaving); BIND (fabric's image, sharing the DC's address as on a host) answering the AD zone through DLZ and fabric's zone unchanged, the DC's signed updates accepted; an RODC joining with fabric's image (NTLM forwarded for accounts it does not cache; with the writable DC down, cached people only, no writes); refusals: unsigned updates in either zone, a site admin in another site or its service accounts, a short or wrong password |
| `devices.py` | Devices and device roles on a real DC through fabric's own functions, as the site's agent account: the default roles made once in the organisation's OU, validation and its refusals, effective permissions and VLAN, role membership, certificate links, the audit log |
| `linux_join.py` | Ubuntu 24.04 and 26.04 joining a real DC with fabric's `join-linux.sh` as rendered: a wrong root-CA fingerprint refused (nothing changed), a join with a site admin's password and one with a one-time join password, fabric's ids, a PAM logon and a Kerberos ticket, sudo for a site admin and not a person, a person of another site refused by the log-on GPO, cached logons with the DC stopped |
| `start_dc.py` | A converged DC for any suite that needs AD (tests/keycloak): fabric's image, hardening, deploy and convergence, a test PKI |
