# tests/federation

| File | What |
|---|---|
| `run.py` | Invitations (made, hashed, listed, withdrawn, expired), the federation endpoint's routes and refusals, a site joining an upstream end to end with the real Step-CA image (pinned root, TLS to the endpoint's name, site CA signed by the root, records on both sides, single use, idempotent re-run), the endpoint socket's uid check |
