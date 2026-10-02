# jinja/adguard/build

Build context of the local image `fabric/adguard:local`, copied (not rendered) to `/opt/adguard/build/` by
`deploy.py`; rebuilt when it changes or when `fabriclib/images/needs_rebuild.py` finds another base.

| File | What |
|---|---|
| `Dockerfile` | AdGuard Home FROM the pinned `image_adguard`, its binary copied without file capabilities, so the container runs with none (no network needed to build) |
