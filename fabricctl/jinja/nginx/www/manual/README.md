# jinja/nginx/www/manual

The in-browser manual, deployed to `/opt/nginx/www/manual/` and served at
`/manual/` on the landing host. `deploy.py` also copies the repository's
`docs/` to `/opt/nginx/www/manual/docs/`, which the page fetches.

| File | What |
|---|---|
| `index.html.j2` | The manual viewer (extends `shared/base.html.j2`) → `index.html`: opens the manual's master index (`docs/README.md`), a tab per volume index, follows the manual's relative links and `#anchors` (GitHub-style heading ids), renders with marked and mermaid; the page shown is kept in the URL (`#<path>[#anchor]`), so reload, back and forward work |
| `marked.min.js` | Vendored marked v15.0.12 (Markdown parser; its banner says so), copied as is; source URL and checksum are not recorded |
| `mermaid.min.js` | Vendored mermaid 10.9.1 (diagrams in the docs; version string inside the bundle), copied as is; source URL and checksum are not recorded |
