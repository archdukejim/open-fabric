# tests/freeradius

| File | What |
|---|---|
| `run.py` | setup's default device roles (created once, a deleted one not brought back); FreeRADIUS on fabric's image and templates against a real domain controller (tests/samba/start_dc), devices made by fabric's directory code and people the way fabric makes them: EAP-TLS (eapol_test) accepted with the role's VLAN (lowest priority wins); refused for a disabled device, an unlinked certificate, a role without the permission, a foreign CA, and at once after unlinking; EAP-TTLS/PAP for people (mapped groups, VLAN by priority; refused: wrong password, locked account after 5 failures, a disabled person, a one-time password not yet changed, no mapped group, unknown name, a password outside the tunnel); MAB (radclient) by permission; unknown clients, wrong secrets and requests without Message-Authenticator get nothing; directory down → refused, back → reconnects; hardening; no secret or password in the logs |
