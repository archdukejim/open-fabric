# fabriclib/security

| File | What |
|---|---|
| `apply_docker_firewall.py` | Rebuild the `DOCKER-USER` chain so only the LAN (and `security.firewall_allow`) can open connections to Docker-published ports; RADIUS clients only to UDP 1812/1813. Run at setup and at boot by `fabric-firewall.service`. |
| `firewall_rules.py` | The networks and interfaces the host firewall opens (SSH, NTP, DHCP), for the setup step and its consent question |
| `ufw_rule.py` | The words of one ufw rule fabric adds (SSH, NTP, DHCP), and the files recording what it opened |
| `hardened_daemon_settings.py` | Docker's `daemon.json` now and with fabric's hardening merged in |
