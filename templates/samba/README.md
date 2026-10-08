# templates/samba

The Samba AD domain controller (manual 2.11.2), deployed to `/opt/samba`.

| File | What |
|---|---|
| `docker-compose.yml.j2` | The DC in the host network: five capabilities, read-only root, its data, secrets, certificate and converge code mounted |
| [admx/](admx/) | fabric's blank starter template for an admin's own policies (`fabricctl gpo starter`) |
