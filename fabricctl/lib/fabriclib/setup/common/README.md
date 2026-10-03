# fabriclib/setup/common

Helpers shared by setup steps and the consent plans.

| File | What |
|---|---|
| `missing_packages.py` | Which Debian packages are not installed |
| `docker_ready.py` | Whether Docker, compose v2 and buildx answer |
| `service_account_name.py` | A service's host account name (`fabric-dns`, …): `service_users.<key>.name` or fabric's default |
| `previous_accounts.py` | The service accounts of releases before 2026-10 (names, ids), which setup moves away from |
