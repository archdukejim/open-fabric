# tests/host

End-to-end test on a real host over SSH (e.g. the reference Raspberry Pi), installing from the `.deb`. **It installs fabric on that host** — use a disposable machine.

| File | What |
|---|---|
| `run.sh` | Package install, setup, doctor, `fabric.target`, certificate page, RFC2136, restricted sign-in, re-run, stop/start (reuses the check scripts in `tests/sandbox/`) |
