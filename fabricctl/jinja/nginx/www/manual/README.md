# jinja/nginx/www/manual

The in-browser manual, deployed to `/opt/nginx/www/manual/` and served at
`/manual/` on the landing host. `deploy.py` also copies the repository's
`docs/` to `/opt/nginx/www/manual/docs/`, which the page fetches.

| File | What |
|---|---|
| `index.html.j2` | The manual viewer (extends `shared/base.html.j2`): loads Markdown from `docs/` and renders it with marked and mermaid → `index.html` |
| `marked.min.js` | Vendored marked (Markdown parser), copied as is |
| `mermaid.min.js` | Vendored mermaid (diagrams in the docs), copied as is |
