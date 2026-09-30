# tests/sandbox

A full install from the `.deb` in a disposable systemd + Docker container
(`sudo tests/run-all.sh sandbox`, ~25 min), then day-2 operations on it.

| File | What |
|---|---|
| `run.sh` | Install, setup, doctor, fabric.target, DHCP (a LAN client leased and registered in `dhcp.<domain>`, `fabricctl dhcp`), 802.1X (`fabricctl radius add-client`, a MAB request answered from the directory with the role's VLAN, `fabricctl radius log`), secrets in OpenBao, RFC2136, sign-in (admin, non-admin, auditor), images update/rollback/prune, re-runs, upgrade of pre-pinning vars, TSIG/ACL, package upgrade/remove, reinstall, uninstall with export + purge (nothing left), restore from the export |
| `Dockerfile` | The sandbox image (systemd + Docker-in-Docker) |
| `login_test.py` | Real sign-in through nginx, Keycloak (password change, TOTP) and the web UI; OpenBao's UI through Keycloak; a role bundle through a directory group |
| `rfc2136_test.sh` | `nsupdate` with a TSIG key: allowed names only, wrong keys refused |
| `certs_page_test.sh` | The certificate page: formats, MIME types, plain HTTP by name and IP |
| `set_lock.py` | Pretend a newer validated image list arrived (edit the installed `images.lock.yaml`) |
| `ldap_has_users.py` | How many of some uids exist in 389-DS (inside the sandbox) |
| `radius_mab.py` | A switch's MAB request (with Message-Authenticator) from outside the sandbox: Accept + VLAN, Reject, or no reply |
| `radius_device.py` | Inside the sandbox: a MAB role and device, made by fabric's own directory code |
| `iterate.sh` | Developer helper: re-run parts against a kept sandbox |
