# tests/sandbox

A full install from the `.deb` in a disposable systemd + Docker container
(`sudo tests/run-all.sh sandbox`, about 30 min), then day-2 operations on it.

| File | What |
|---|---|
| `run.sh` | Install, setup, doctor, fabric.target, DHCP (a LAN client leased and registered in `dhcp.<domain>`, `fabricctl dhcp`), 802.1X (`fabricctl radius add-client`, a MAB request answered from the directory with the role's VLAN, `fabricctl radius log`, `map-group` turning EAP-TTLS on), POSIX identities (the admin's; people created outside fabric through `fabricctl directory sync`), secrets in OpenBao, OpenBao unlock/restart/rotation (core services serve while it is down), RFC2136, sign-in (admin, non-admin, auditor), images update/rollback/prune, re-runs, upgrade of pre-pinning vars, TSIG/ACL, package upgrade/remove, reinstall, uninstall with export + purge (nothing left), restore from the export |
| `Dockerfile` | The sandbox image (systemd + Docker-in-Docker) |
| `login_test.py` | Real sign-in through nginx, Keycloak (password change, TOTP) and the web UI, and the refusals; OpenBao's UI through Keycloak; a role bundle through a directory group; adding a person and resetting a sign-in |
| `posix_check.py` | A person's POSIX attributes as 389-DS has them (read inside the box) |
| `rfc2136_test.sh` | `nsupdate` with a TSIG key: allowed name accepted and served, other names and wrong keys refused |
| `certs_page_test.sh` | The certificate page: formats, MIME types, plain HTTP by name and IP |
| `set_lock.py` | Pretend a newer validated image list arrived (edit the installed `images.lock.yaml`) |
| `ldap_has_users.py` | How many of some uids exist in 389-DS (inside the sandbox) |
| `radius_mab.py` | A switch's MAB request (with Message-Authenticator) from outside the sandbox: Accept + VLAN, Reject, or no reply |
| `radius_device.py` | Inside the sandbox: VLAN 30 on the default `printers` role and a printer in it, with fabric's own directory code |
| `list_roles.py` | Inside the sandbox: the device roles' names (the defaults setup created) |
| `iterate.sh` | Developer helper: re-run parts against a kept sandbox |
