# templates/webui-app

The page templates (Jinja2, rendered by `views/render_page.py` with autoescape; no inline script or style, so pages work under the strict Content-Security-Policy). `base.html` is the frame every page extends.

| File | What |
|---|---|
| `apply.html` | The apply page |
| `audit.html` | The audit page |
| `base.html` | The frame: header, tabs (only those the person may see), footer |
| `bind9.html` | The bind9 page |
| `continue.html` | The continue page |
| `dirsrv.html` | The dirsrv page |
| `dirsrv_macros.html` | Macros for the device and role forms |
| `error.html` | The error page |
| `freeradius.html` | The freeradius page |
| `kea.html` | The kea page |
| `openbao.html` | The openbao page |
| `overview.html` | The overview page |
| `person_result.html` | The person result page |
| `pki_result.html` | The pki result page |
| `radius_secret.html` | The radius secret page |
| `stepca.html` | The stepca page |
| `tsig_result.html` | The tsig result page |
