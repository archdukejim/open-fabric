# fabriclib/security

| File | What |
|---|---|
| `apply_docker_firewall.py` | Rebuild the `DOCKER-USER` chain so only the LAN (and `security.firewall_allow`) can open connections to Docker-published ports. Run at setup and at boot by `fabric-firewall.service`. |
