# fabriclib/directory

fabric's directory on Samba AD (manual 1.6.3, 2.11.2.16): what fabric-agent, setup and the web UI ask of it. Every
operation runs inside the DC (`src/containers/samba/directory_op.py`), signed in as this site's `fabric-agent`
account, so AD's per-site limits apply to it.

| File | What |
|---|---|
| `__init__.py` | Package marker |
| `run_op.py` | Run one directory operation as the site's agent account; refusals as messages safe to show |
