# jinja/nginx/www/shared

| File | What |
|---|---|
| `base.html.j2` | Base layout every page extends (`{% extends "../shared/base.html.j2" %}`, resolved by `jinja_env`'s relative paths); not rendered on its own |
| `style.css` (in `static/nginx/`) | The stylesheet for every page, copied as is → `/opt/nginx/www/shared/style.css`, served as `/style.css` |
