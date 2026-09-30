# jinja/keycloak/build

Build context of the local image `fabric/keycloak:local`, copied (not
rendered) to `/opt/keycloak/build/` by `deploy.py`; rebuilt when it changes or
its base differs (`fabriclib/images/needs_rebuild.py`).

| File | What |
|---|---|
| `Dockerfile` | Runs `kc.sh build` with fabric's build-time options on `BASE_IMAGE` (pinned `image_keycloak`), so the container starts `--optimized` with a read-only root; label `org.fabric.base` |
| `.dockerignore` | Keeps `__pycache__` and `*.pyc` out of the build context |
