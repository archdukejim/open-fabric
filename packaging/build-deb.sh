#!/bin/bash
# -----------------------------------------------------------------------
# Build the fabricctl .deb (Architecture: all — one package for amd64 and
# arm64) from this checkout.
#
#   packaging/build-deb.sh            -> dist/fabricctl_<version>_all.deb
#   DEB_VERSION=1.6.0 packaging/...   exact version (releases)
#
# Default version: fabric/VERSION when HEAD is tagged v<VERSION> and the tree
# is clean, else <VERSION>~git<UTC timestamp>.<commit> (sorts below the
# release, above earlier dev builds, so apt upgrades work while testing).
# Needs: dpkg-deb, git, tar. Committed and uncommitted (not ignored) files
# are packaged, like the sandbox tests use them.
# -----------------------------------------------------------------------
set -euo pipefail
REPO="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${OUT:-$REPO/dist}"
BASE_VERSION="$(tr -d ' \n' < "$REPO/fabric/VERSION")"
COMMIT="$(git -C "$REPO" rev-parse --short HEAD 2>/dev/null || echo unknown)"
DIRTY=""
git -C "$REPO" diff --quiet HEAD 2>/dev/null || DIRTY="-dirty"
if [ -z "${DEB_VERSION:-}" ]; then
    if [ -z "$DIRTY" ] && git -C "$REPO" describe --exact-match --tags HEAD 2>/dev/null | grep -qx "v$BASE_VERSION"; then
        DEB_VERSION="$BASE_VERSION"
    else
        DEB_VERSION="${BASE_VERSION}~git$(date -u +%Y%m%d%H%M%S).${COMMIT}"
    fi
fi

stage="$(mktemp -d)"; trap 'rm -rf "$stage"' EXIT
root="$stage/fabricctl"
lib="$root/usr/lib/fabricctl"
mkdir -p "$lib" "$root/usr/bin" "$root/usr/share/doc/fabricctl/examples" "$root/DEBIAN"

# The fabric tree + docs exactly as tracked (no ignored files: no secrets,
# no custom-vars.yaml, no __pycache__).
# Files deleted in the working tree but not yet staged are skipped.
(cd "$REPO" && git ls-files -z --cached --others --exclude-standard -- fabric docs LICENSE README.md \
    | while IFS= read -r -d '' f; do [ -e "$f" ] && printf '%s\0' "$f"; done \
    | tar --null -T - -cf -) | tar -xf - -C "$lib"
find "$lib" -name __pycache__ -prune -exec rm -rf {} +
{
    echo "commit: ${COMMIT}${DIRTY}"
    echo "built:  $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    echo "package: fabricctl ${DEB_VERSION}"
} > "$lib/fabric/BUILD"

install -m 0755 "$REPO/packaging/deb/fabricctl" "$root/usr/bin/fabricctl"
install -m 0644 "$REPO/custom-vars-tpl.yml" "$root/usr/share/doc/fabricctl/examples/vars.yaml"
install -m 0644 "$REPO/LICENSE" "$root/usr/share/doc/fabricctl/copyright"
sed "s/@VERSION@/${DEB_VERSION}/" "$REPO/packaging/deb/control.in" > "$root/DEBIAN/control"
install -m 0755 "$REPO/packaging/deb/postinst" "$root/DEBIAN/postinst"

# Code is root-owned and not writable by anyone else; scripts executable.
find "$lib" -type d -exec chmod 0755 {} +
find "$lib" -type f -exec chmod 0644 {} +
find "$lib" -type f -name '*.sh' -exec chmod 0755 {} +
(cd "$root" && find usr -type f -exec md5sum {} + > DEBIAN/md5sums)

mkdir -p "$OUT"
deb="$OUT/fabricctl_${DEB_VERSION}_all.deb"
dpkg-deb --root-owner-group -Zxz --build "$root" "$deb" >/dev/null
echo "$deb"
