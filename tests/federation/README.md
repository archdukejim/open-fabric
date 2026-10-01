# tests/federation

| File | What |
|---|---|
| `run.py` | Invitations (made, hashed, listed, withdrawn, expired), the federation endpoint's routes and refusals, a site joining an upstream end to end with the real Step-CA image (pinned root, TLS to the endpoint's name, site CA signed by the root, records on both sides, single use, idempotent re-run), the endpoint socket's uid check; runs `nested.py` at the end |
| `nested.py` | Nesting and re-parenting with three installs side by side: a root of path length 2 invites `lab` with `--nest 1`, lab invites `lab2` nested under it, lab2's CA and devices chain to the root through lab, lab2 moves under the root; nesting deeper than a CA allows and a path-length-0 site inviting are refused |
| `role.py` | One install's federation side for `nested.py` (invite, signing capacity, the endpoint over TLS), imported from that install's own tree |
