# jinja/nginx/www/ldap

Rendered by `deploy.py` to `/opt/nginx/www/ldap/`, served at `/ldap/` on the
landing host.

| File | What |
|---|---|
| `index.html.j2` | LDAP client guide: user management architecture, Ubuntu auto-install, manual SSSD setup, smart card mapping → `index.html` |
| `install-ldap.sh.j2` | Ubuntu client installer: fetches the root CA, installs and configures SSSD/PAM against fabric's LDAP → `install-ldap.sh` (served as `/ldap/install-ldap-<domain_file>.sh`) |
