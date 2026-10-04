# src/ux

Thin entry points, one folder per UX variant (global Rule 7.2, decision D27): they parse input and call the
shared code, nothing more (manual 1.10.1.3).

| Path | What |
|---|---|
| [cli/](cli/) | The `fabricctl` command and the scripts it runs |
| [web/](web/) | What starts the web UI (`src/webui/`) |
