# jinja/systemd

Host systemd units, rendered or copied by `deploy.py` to `/etc/systemd/system/`.

| File | What |
|---|---|
| `wrapper.service.j2` | One unit per installed service (nginx, bind9, stepca, ldap, postgres, keycloak, fabric-web, openbao, fluentbit, kea, freeradius): `docker compose up` of `/opt/<folder>/docker-compose.yml`, part of `fabric.target`, waits for the container to be healthy, optional ExecCondition/ExecStartPost (OpenBao unlock) → `<service>.service` |
| `fabric.target` | Groups every fabric unit (`systemctl start/stop/restart fabric.target`), copied as is → `fabric.target` |
| `fabric-agent.service.j2` | The root `fabric-agent` (`lib/agent/server.py`): the web UI's privileged API on a unix socket only; only with `install_webui` → `fabric-agent.service` |
