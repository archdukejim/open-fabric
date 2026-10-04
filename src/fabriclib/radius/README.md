# fabriclib/radius

Optional 802.1X with FreeRADIUS (design §6): RADIUS clients in `vars.yaml`
(`radius_clients`), their secrets in OpenBao (`radius_secrets`), the
decisions from FreeRADIUS's journal. Who may join is the device RBAC in
389-DS (`fabriclib/ldap`); the policy itself runs in the container
(`src/containers/freeradius`).

| File | What |
|---|---|
| `normalize_radius_people.py` | Check `radius_people`: groups whose members may join by password, VLAN, priority |
| `map_radius_group.py` | Let a group's members join by password (EAP-TTLS), optionally on a VLAN (locked, audited) |
| `unmap_radius_group.py` | Stop a group joining by password (locked, audited) |
| `normalize_radius_clients.py` | Check `radius_clients` (name, address or network, no overlaps, Message-Authenticator); a secret in the vars file is taken out for OpenBao |
| `deploy_freeradius.py` | FreeRADIUS's config (client secrets, the directory account) and the policy code under `<deploy_base>/freeradius` (its certificates and CA bundle come from setup's certificate step) |
| `add_radius_client.py` | Add a switch or access point; its secret (given, or new) into fabric's secrets (OpenBao); locked, audited |
| `rotate_radius_secret.py` | A new shared secret for a client (given, or random); audited |
| `remove_radius_client.py` | Remove a client and delete its secret; audited |
| `list_auth_log.py` | Recent decisions (accepted / refused and why) from the journal (`journalctl -t freeradius`) |
| `radius_overview.py` | What the FreeRADIUS tab and `fabricctl radius status` show |
| `radius_guides.py` | What the tab's setup guides show, filled in for this install (server IP and name, clients, mapped groups, Windows scripts) |
| `windows_setup_script.py` | A PowerShell script that sets a Windows PC up for 802.1X (Wired AutoConfig, the fabric root CA, the device's .p12, the profile) |
| `windows_lan_profile.py` | The wired 802.1X profile for Windows: EAP-TLS (machine certificate) or EAP-TTLS/PAP, pinned to the server name and root CA |
| `run_radius_command.py` | `fabricctl radius status / log / add-client / rotate-secret / remove-client / map-group / unmap-group` |
