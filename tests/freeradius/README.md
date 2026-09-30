# tests/freeradius

| File | What |
|---|---|
| `run.py` | FreeRADIUS on fabric's image and templates against a real 389-DS with fabric's seed, devices made by fabric's directory code: EAP-TLS (eapol_test) accepted with the role's VLAN (lowest priority wins); refused for a disabled device, an unlinked certificate, a role without the permission, a foreign CA, and at once after unlinking; MAB (radclient) by permission; unknown clients, wrong secrets and requests without Message-Authenticator get nothing; directory down → refused, back → reconnects; hardening; no secret in the logs |
