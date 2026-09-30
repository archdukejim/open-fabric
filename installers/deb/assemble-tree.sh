#!/bin/bash
# -----------------------------------------------------------------------
# Assemble the installed tree from the repository's product folders — the
# one place that knows how they map (the .deb build and the tests that
# need an installed-looking tree both use it):
#
#   fabricctl/*                 -> <dest>/fabric/            (examples/ excepted: shipped as docs)
#   webui/*  (the web UI app)   -> <dest>/fabric/lib/webui/
#   webui/Dockerfile, .dockerignore
#                               -> <dest>/fabric/jinja/webui/build/   (its image build context)
#   docs/, LICENSE, README.md   -> <dest>/
#
# The installed layout (/usr/lib/fabricctl/fabric, /opt/fabric) is the same
# as before the repository was split (design D25): installs upgrade in place.
# Tracked and untracked-but-not-ignored files only: never secrets, local
# vars or __pycache__. Needs git and GNU tar.
#
#   installers/deb/assemble-tree.sh <dest>
# -----------------------------------------------------------------------
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
DEST="${1:?usage: assemble-tree.sh <dest>}"
mkdir -p "$DEST"

# files under the given paths as git sees them (deleted-but-unstaged ones skipped), NUL-separated
files() {
    (cd "$REPO" && git ls-files -z --cached --others --exclude-standard -- "$@" \
        | while IFS= read -r -d '' f; do [ -e "$f" ] && printf '%s\0' "$f"; done)
}
copy() {  # copy <tar --transform expression> <paths...>
    local expr="$1"; shift
    files "$@" | (cd "$REPO" && tar --null -T - -cf -) | tar -xf - -C "$DEST" --transform "$expr"
}

copy 's,^fabricctl/,fabric/,' fabricctl
rm -rf "$DEST/fabric/examples"
copy 's,^webui/Dockerfile$,fabric/jinja/webui/build/Dockerfile,;s,^webui/\.dockerignore$,fabric/jinja/webui/build/.dockerignore,;s,^webui/,fabric/lib/webui/,' webui
copy 's,^,,' docs LICENSE README.md
find "$DEST" -name __pycache__ -prune -exec rm -rf {} +
