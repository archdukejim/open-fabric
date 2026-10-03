#!/bin/bash
# -----------------------------------------------------------------------
# Install fabric on THIS host from a git checkout, the same way a release
# installs: build the .deb from the checkout (packaging/deb/build-deb.sh), install it with
# apt (dependencies resolved), then run `fabricctl setup`.
#
#   sudo scripts/install-from-checkout.sh                         interactive
#   sudo scripts/install-from-checkout.sh --file vars.yaml        answers from a file
#   sudo scripts/install-from-checkout.sh --file vars.yaml --non-interactive --yes --approve all
#
# Arguments go to `fabricctl setup`; without --file, the checkout's custom-vars.yaml
# (if present) is used. Afterwards use `sudo fabricctl ...`
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
deb="$(OUT="$out" bash "$HERE/../packaging/deb/build-deb.sh")"
echo "installing $(basename "$deb")"
DEBIAN_FRONTEND=noninteractive apt-get install -y -qq "$deb"

# The checkout's own custom-vars.yaml (git-ignored, never packaged) is the
# answers file unless one is given: setup now runs from the package, which
# cannot see the checkout.
case " $* " in
    *" --file "*|*" --file="*) ;;
    *) vars="$(cd "$HERE/.." && pwd)/custom-vars.yaml"
       if [ -f "$vars" ]; then
           echo "using $vars"
           set -- --file "$vars" "$@"
       fi ;;
esac
exec fabricctl setup "$@"
