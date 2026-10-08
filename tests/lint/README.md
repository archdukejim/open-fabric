# tests/lint

| File | What |
|---|---|
| `run.sh` | ruff on `src/`, `scripts/` and `tests/` (rules in the root `pyproject.toml`), shellcheck on every shell script (the tests' eval-only findings excepted); both from images pinned by digest (decision 2.1.1.15, manual 3.1.2) |
