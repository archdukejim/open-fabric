# src/webui/views

Every page (Jinja2 templates in ../templates, autoescaped, no inline script or style) and the stylesheet; hides tabs, menus and forms the person has no permission for. `from webui import views` imports them all.

| File | What |
|---|---|
| `apply_result.py` | The page after Apply: whether it worked and its output. |
| `audit.py` | The audit log page, newest first. |
| `b64.py` | Base64-encode a text for a data: download link. |
| `bind9.py` | The BIND9 tab: forward zone records and the add form, generated reverse zones, or TSIG keys. |
| `constants.py` | What the pages show: tabs, sections, sub-menus, the permissions that show them. |
| `continue_page.py` | The 'Signed in' page that moves on to the target with a meta refresh and a link. |
| `css.py` | The whole stylesheet (static/webui-app/app.css), served as /static/app.css (light and dark colour schemes). |
| `dirsrv.py` | The 389-DS tab: devices, one device, roles, one role, or people and groups. |
| `error_page.py` | The error page: status, message and a 'Sign in again' link. |
| `freeradius.py` | The FreeRADIUS tab: overview (server, people groups, RADIUS clients, recent decisions) or a setup guide for switches or Windows. |
| `kea.py` | The Kea tab: subnets, reservations with add/remove forms, and leases — or how to turn DHCP on. |
| `openbao.py` | The OpenBao tab: status, unlock methods (with add, rotate and remove views), secrets, disk encryption guide. |
| `overview.py` | The Overview tab: one tile per service with a traffic light and a link to its tab. |
| `person_result.py` | The page that shows a person's one-time password once, after creating them or resetting their sign-in. |
| `pki_result.py` | The result page after signing, issuing or converting a certificate: details and every format as a download. |
| `radius_secret.py` | The page that shows a RADIUS client's shared secret once, after adding it or making a new one. |
| `render_page.py` | Render one template with the common page variables, hiding the tabs, sub-menus and forms the signed-in person has no permission for. |
| `stepca.py` | The Step-CA tab: CA details, sign a CSR, new key + certificate, inspect, convert, or the issued list. |
| `tsig_result.py` | The page that shows a TSIG key's secret and RFC2136 client settings once. |
| `__init__.py` | Imports every function of this folder, so callers keep `module.function` |
