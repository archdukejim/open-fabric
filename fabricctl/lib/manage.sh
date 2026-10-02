#!/bin/bash
# -----------------------------------------------------------------------
# manage.sh — the install's side of the `fabricctl` command (/usr/bin/fabricctl runs it on a set-up host).
# Everything is fabriclib/cli.py; with no arguments it opens the vars editor (`fabricctl --interactive`).
# `fabricctl help` lists the commands.
# -----------------------------------------------------------------------
set -euo pipefail
FABRIC_DIR="$(dirname "$(dirname "$(readlink -f "${BASH_SOURCE[0]}")")")"
[ $# -eq 0 ] && set -- --interactive
exec python3 "$FABRIC_DIR/lib/fabriclib/cli.py" "$@"
