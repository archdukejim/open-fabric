# jinja/dirsrv/build

Build context of the local image `fabric/dirsrv:local`, copied (not rendered)
to `/opt/dirsrv/build/` by `deploy.py`; rebuilt when it changes or its base
differs (`fabriclib/images/needs_rebuild.py`).

| File | What |
|---|---|
| `Dockerfile` | 389-ds-base, python3-lib389 and tini from Debian on `BASE_IMAGE` (pinned `image_debian`); fabric's ldap uid/gid; instance state under `/data`; label `org.fabric.base` |
| `dscontainer-launch.py` | The image's entry point (under tini): runs upstream `dscontainer -r` with its SIGCHLD handler disabled, which otherwise crashes first start at random → `/usr/local/bin/dscontainer-launch.py` in the image |
| `.dockerignore` | Keeps `__pycache__` and `*.pyc` out of the build context |
