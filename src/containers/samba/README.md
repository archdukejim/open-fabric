# src/containers/samba

Code that runs inside the Samba AD domain controller (manual 2.11.2.15, S1.3), copied to `<deploy_base>/samba/converge`
and mounted read-only. It runs as root inside the DC on its own database: no credentials, no network.

| File | What |
|---|---|
| `converge.py` | The entry point: the wanted state as JSON on stdin, every part in order, what changed as JSON |
| `open_samdb.py` | The DC's database opened locally as the system (optionally allowing schema changes) |
| `ensure_schema.py` | fabric's and sudo's attributes and classes in AD's schema, added once (OIDs AD accepts, Q3) |
| `ensure_layout.py` | `OU=sites`, the site's OU tree, `OU=organisation` at the root site; new users and computers into it |
| `ensure_groups.py` | `<site>-users`, `<site>-admins`; `fabric-admins`, `fabric-break-glass` at the root site |
| `ensure_site_acl.py` | The site's admins: full control of their site's OU, nothing on its service accounts (Q4) |
| `ensure_ad_site.py` | The AD site of this fabric site and its subnets from the address plan |
| `set_password_policy.py` | The admin's password policy on the domain object (D89) |
| `ensure_gpo.py` | One of fabric's GPOs created, linked, its SYSVOL files written, its version bumped on change |
| `root_ca_policy.py` | The Registry.pol that makes fabric's root CA a trusted root on Windows (Q13) |
| `logon_rights_policy.py` | The GptTmpl.inf granting log-on to a site's machines (D90, Q16) |
