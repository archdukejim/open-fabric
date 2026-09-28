#!/bin/bash
# -----------------------------------------------------------------------
# fabric bootstrap: install fabric on THIS host from a git checkout.
#
#   sudo ./setup.sh                          interactive
#   sudo ./setup.sh --file vars.yaml         answers from a file
#   sudo ./setup.sh --file vars.yaml --non-interactive --yes
#
# Only makes sure Python's YAML and Jinja2 are present, then hands over to
# `fabricctl setup` (fabric/lib/fabriclib/setup/). Once installed, use
# `sudo fabricctl setup|doctor|certs|uninstall|reinstall` directly (also
# accepted here: sudo ./setup.sh uninstall).
# -----------------------------------------------------------------------
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root: sudo $0 $*" >&2
    exit 1
fi

# Stamp the build so the installed fabricctl reports exactly what it runs.
{
    echo "commit: $(git -C "$HERE" rev-parse --short HEAD 2>/dev/null || echo unknown)$(git -C "$HERE" diff --quiet HEAD 2>/dev/null || echo '-dirty')"
    echo "built:  $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
} > "$HERE/fabric/BUILD"

if ! python3 -c 'import yaml, jinja2' 2>/dev/null; then
    echo "Installing python3-yaml and python3-jinja2..."
    DEBIAN_FRONTEND=noninteractive apt-get update -qq
    DEBIAN_FRONTEND=noninteractive apt-get install -y -qq python3-yaml python3-jinja2
fi

case "${1:-}" in
    setup|doctor|certs|client-cert|tsig|acl|status|start|stop|restart|uninstall|reinstall)
        exec python3 "$HERE/fabric/lib/fabriclib/cli.py" "$@" ;;
esac
exec python3 "$HERE/fabric/lib/fabriclib/cli.py" setup "$@"
