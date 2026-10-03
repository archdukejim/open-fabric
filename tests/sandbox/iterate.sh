#!/bin/bash
# Developer loop: package the current working tree, install it into a sandbox
# left running by `KEEP=1 tests/sandbox/run.sh` and re-run setup there (setup
# is idempotent, so finished steps are quick). Extra args go to setup, e.g.
#   sudo tests/sandbox/iterate.sh --step certs --step start
set -uo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
NAME=fabric-sandbox
docker ps --format '{{.Names}}' | grep -qx "$NAME" || { echo "no running sandbox; run KEEP=1 tests/sandbox/run.sh" >&2; exit 2; }
out=$(mktemp -d)
deb=$(OUT="$out" bash "$REPO/packaging/deb/build-deb.sh") || exit 1
docker cp "$deb" "$NAME:/root/fabricctl-dev.deb"; rm -rf "$out"
docker exec "$NAME" bash -c 'DEBIAN_FRONTEND=noninteractive apt-get install -y -qq /root/fabricctl-dev.deb >/dev/null'
if [ $# -eq 0 ]; then set -- --file /root/vars.yaml; fi
docker exec "$NAME" bash -lc "fabricctl setup --non-interactive --yes $*"
