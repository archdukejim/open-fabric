# jinja/kea/build

Build context of the local image `fabric/kea:local`, copied (not rendered) to
`/opt/kea/build/` by `deploy.py`; rebuilt when it changes, its base differs or
the pinned Kea version changes (`fabriclib/images/needs_rebuild.py`, label
`org.fabric.kea`).

| File | What |
|---|---|
| `Dockerfile` | Kea DHCPv4 + DHCP-DDNS from ISC's apt repository on `BASE_IMAGE` (pinned `image_debian`); refuses a repository key whose fingerprint is not the pinned one and installs exactly `KEA_VERSION` (both from `packages:` in images.lock.yaml) |
