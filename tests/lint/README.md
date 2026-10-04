# tests/lint

| File | What |
|---|---|
| `run.sh` | ruff on `src/`, `scripts/` and `tests/` (rules in the root `pyproject.toml`), shellcheck on every shell script (the tests' eval-only findings excepted); both from images pinned by digest (decision D34, manual 4.8.2) |
