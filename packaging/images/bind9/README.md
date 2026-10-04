# jinja/bind9/build

Build context of the local image `fabric/bind9:local`, copied (not rendered)
to `/opt/bind9/build/` by `deploy.py`; rebuilt when it changes or when
`fabriclib/images/needs_rebuild.py` finds another base.

| File | What |
|---|---|
| `Dockerfile` | bind9 + bind9-utils from Debian on `BASE_IMAGE` (digest-pinned `image_debian`), fabric's bind uid/gid baked in, label `org.fabric.base` |
| `.dockerignore` | Keeps `__pycache__` and `*.pyc` out of the build context |
