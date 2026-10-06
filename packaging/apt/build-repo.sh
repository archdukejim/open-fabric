#!/bin/bash
# -----------------------------------------------------------------------
# Build fabric's signed apt repository (manual 1.4.1.1, D7) with reprepro:
# suite `stable` from the released packages, suite `testing` from a release
# candidate's, signed with the repository key. Only the published tree is
# written to <out>: dists/, pool/ and public.key (reprepro's conf/ and db/
# stay in a temporary folder).
#
#   GPG_PRIVATE_KEY=<armored key> GPG_PASSPHRASE=<its passphrase> \
#     packaging/apt/build-repo.sh <out> <stable-debs-dir> [<testing-debs-dir>]
#
# The key comes from the environment (Actions secrets), never a command line.
# -----------------------------------------------------------------------
set -euo pipefail
OUT="${1:?usage: build-repo.sh <out> <stable-debs-dir> [<testing-debs-dir>]}"
STABLE="${2:?the folder of the released .deb files}"
TESTING="${3:-}"
: "${GPG_PRIVATE_KEY:?the signing key of the repository, armored}"
HERE="$(cd "$(dirname "$0")" && pwd)"
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT

# the key in a throwaway keyring; its passphrase given to gpg-agent once, so reprepro signs without asking
export GNUPGHOME="$WORK/gnupg"
mkdir -m 0700 "$GNUPGHOME"
echo "allow-preset-passphrase" > "$GNUPGHOME/gpg-agent.conf"
printf '%s\n' "$GPG_PRIVATE_KEY" | gpg --batch --quiet --import
if [ -n "${GPG_PASSPHRASE:-}" ]; then
    for grip in $(gpg --batch --with-colons --with-keygrip --list-secret-keys | awk -F: '$1 == "grp" {print $10}'); do
        printf '%s' "$GPG_PASSPHRASE" | /usr/lib/gnupg/gpg-preset-passphrase --preset "$grip"
    done
fi

mkdir -p "$WORK/repo/conf"
cp "$HERE/distributions" "$WORK/repo/conf/distributions"
shopt -s nullglob
for deb in "$STABLE"/*.deb; do
    reprepro -b "$WORK/repo" includedeb stable "$deb"
done
if [ -n "$TESTING" ]; then
    for deb in "$TESTING"/*.deb; do
        reprepro -b "$WORK/repo" includedeb testing "$deb"
    done
fi
reprepro -b "$WORK/repo" export          # a suite with no package still gets signed indexes

rm -rf "$OUT"
mkdir -p "$OUT"
cp -a "$WORK/repo/dists" "$WORK/repo/pool" "$OUT/" 2>/dev/null || cp -a "$WORK/repo/dists" "$OUT/"
gpg --batch --armor --export > "$OUT/public.key"
touch "$OUT/.nojekyll"                    # GitHub Pages serves the tree as it is
echo "$OUT"
