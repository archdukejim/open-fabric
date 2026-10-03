# jinja/stepca/build

Build context of the local image `fabric/stepca:local`, copied (not rendered)
to `/opt/stepca/build/` by `deploy.py`; rebuilt when it changes or its base
differs (`fabriclib/images/needs_rebuild.py`).

| File | What |
|---|---|
| `Dockerfile` | Copies `/usr/local/bin/step-ca` on `BASE_IMAGE` (pinned `image_stepca`) to drop its cap_net_bind_service file capability, so it runs with no capabilities and no-new-privileges; label `org.fabric.base` |
| `.dockerignore` | Keeps `__pycache__` and `*.pyc` out of the build context |
