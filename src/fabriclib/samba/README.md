# fabriclib/samba

The optional Windows domain: a Samba AD domain controller on the host's address (manual 2.11.2, 1.6.3). The DC
itself is a container (`templates/samba`, `packaging/images/samba`); what converges the domain runs inside it
(`src/containers/samba`).

| File | What |
|---|---|
| `__init__.py` | Package marker |
| `deploy_samba.py` | The DC's files under `<deploy_base>/samba`: root-only folders, the Administrator's password file, the converge code |
