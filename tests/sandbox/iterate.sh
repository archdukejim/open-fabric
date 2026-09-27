#!/bin/bash
# Developer loop: push the current working tree into a sandbox left running
# by `KEEP=1 tests/sandbox/run.sh` and re-run setup there (setup is
# idempotent, so finished steps are quick). Extra args go to setup, e.g.
#   sudo tests/sandbox/iterate.sh --step certs --step start
set -uo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
NAME=fabric-sandbox
docker ps --format '{{.Names}}' | grep -qx "$NAME" || { echo "no running sandbox; run KEEP=1 tests/sandbox/run.sh" >&2; exit 2; }
tmp=$(mktemp)
(cd "$REPO" && git ls-files -z --cached --others --exclude-standard | tar --null -T - -cf "$tmp")
docker cp "$tmp" "$NAME:/root/src.tar"; rm -f "$tmp"
docker exec "$NAME" bash -c 'tar -xf /root/src.tar -C /root/fabric && rm /root/src.tar'
if [ $# -eq 0 ]; then set -- --file /root/vars.yaml; fi
docker exec "$NAME" bash -lc "cd /root/fabric && ./setup.sh --non-interactive --yes $*"
