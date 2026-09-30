# fabriclib/security

| File | What |
|---|---|
| `apply_docker_firewall.py` | Rebuild the `DOCKER-USER` chain so only the LAN (and `security.firewall_allow`) can open connections to Docker-published ports; RADIUS clients only to UDP 1812/1813. Run at setup and at boot by `fabric-firewall.service`. |
