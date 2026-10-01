# fabricctl/lib/federation

| File | What |
|---|---|
| `server.py` | `fabric-federation`: the federation endpoint other sites reach through nginx (`federation.<domain>`) — a minimal root service on a unix socket (nginx's uid and root only) serving `GET /v1/health` and `POST /v1/join`; every route is one fabriclib operation |
| `__init__.py` | Package marker (empty) |
