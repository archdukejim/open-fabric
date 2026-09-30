#!/bin/bash
# -----------------------------------------------------------------------
# Install fabric on THIS host from a git checkout, the same way a release
# installs: build the .deb from the checkout (build-deb.sh), install it with
# apt (dependencies resolved), then run `fabricctl setup`.
#
#   sudo installers/deb/install-from-checkout.sh                         interactive
#   sudo installers/deb/install-from-checkout.sh --file vars.yaml        answers from a file
#   sudo installers/deb/install-from-checkout.sh --file vars.yaml --non-interactive --yes
#
# Arguments go to `fabricctl setup`. Afterwards use `sudo fabricctl ...`
# directly; running this again upgrades to the checkout's current code.
# -----------------------------------------------------------------------
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [ "$(id -u)" -ne 0 ]; then
    echo "Run as root: sudo $0 $*" >&2
    exit 1
fi
for tool in dpkg-deb git tar; do
    command -v "$tool" >/dev/null || { echo "needs $tool (apt install $tool)" >&2; exit 1; }
done

out="$(mktemp -d)"; trap 'rm -rf "$out"' EXIT
deb="$(OUT="$out" bash "$HERE/build-deb.sh")"
echo "installing $(basename "$deb")"
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$deb"
exec fabricctl setup "$@"
