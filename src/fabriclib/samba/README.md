# fabriclib/samba

The optional Windows domain: a Samba AD domain controller on the host's address (manual 2.11.2, 1.6.3). The DC
itself is a container (`templates/samba`, `packaging/images/samba`); what converges the domain runs inside it
(`src/containers/samba`).

| File | What |
|---|---|
| `__init__.py` | Package marker |
| `deploy_samba.py` | The DC's files under `<deploy_base>/samba`: root-only folders, the Administrator's password file, the converge code |
| `write_bind_dlz.py` | What BIND includes for the AD zone: Samba's DLZ module and the update keytab, once the domain exists (empty before) |
| `converge_domain.py` | The wanted state handed to the converge code inside the running DC; what changed (after every start and apply) |
| `domain_status.py` | What `fabricctl domain status` shows: the DC, whether it runs, its roles, the policy in force |
| `set_domain_password_policy.py` | Change the password policy in the settings (checked whole, audited); the next apply writes it |
| `run_domain_command.py` | `fabricctl domain status` and `password-policy` (routing only) |
