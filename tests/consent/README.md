# tests/consent

| File | What |
|---|---|
| `run.py` | Asking before fabric changes the host (host-consent.md), no containers: unattended runs stop without `--approve` and approve nothing; `--approve all`; a re-run asks only about new changes; a declined recommended group is skipped with a warning and shown as a relaxation, a declined required one stops; the interactive question has no default; the `fabric-*` accounts in 600–649, an id taken by another account refused, the move from the previous `bind` (53) account; an older install's settings upgraded; the firewall question rule by rule |
