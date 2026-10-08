# src/ux/web

What starts the web UI. On a host both sit in the package `webui/` (`lib/webui/`); the image runs `server.py`.

| File | What |
|---|---|
| `server.py` | The web UI's server: loads its config, points the agent client at fabric-agent, serves HTTP on nginx's unix socket |
| `devserver.py` | The dev preview (manual 3.1.3): the real pages on sample data and a fake agent, never in production |
