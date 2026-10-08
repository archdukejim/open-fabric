# tests/images

| File | What |
|---|---|
| `run.sh` | The suite: runs the two below, then the build plan (`packaging/docker-bake.hcl`) against a default host's rendered compose files, an unpinned base refused, every image built and smoke tested, the smoke test refusing the upstream step-ca (decision 2.1.1.21, manual 3.14.1) |
| `published.py` | Which image a host runs, rendered through the real templates: local builds without digests, published images with them, a local build again for custom ids (2.1.14.5); the lock's ids against the Dockerfiles and defaults (manual 1.14.3) |
| `verify.py` | Signature verification against real keyless signatures: a signed image verifies with its signer and is refused with fabric's; unsigned, unreachable and unpinned refs refused; the deploy step and its opt-out (2.1.14.6, 2.1.14.10, 2.1.14.11) |
