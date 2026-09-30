# jinja/nginx/www/landing

| File | What |
|---|---|
| `index.html.j2` | The landing page (extends `shared/base.html.j2`): links to the manual, the CA certificate page and the LDAP guide, plus the admin's `links` (link-vars.yaml) → `/opt/nginx/www/landing/index.html`, served at `https://<hostname_landing>/` |
