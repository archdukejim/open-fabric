#!/bin/bash
# -----------------------------------------------------------------------
# Stage the build contexts of fabric's own images (decision D41, manual
# 4.7.1) exactly as a host has them: the installed tree is assembled
# (assemble-tree.sh), each image's context is its jinja/<image>/build
# folder, and the web UI's gets the app in app/ (as
# deploy/install_service_units does on a host). packaging/docker-bake.hcl
# builds from <dest>/<image>.
#
#   packaging/images/stage-contexts.sh <dest>
# -----------------------------------------------------------------------
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
DEST="${1:?usage: stage-contexts.sh <dest>}"
TREE="$(mktemp -d)"
trap 'rm -rf "$TREE"' EXIT

bash "$REPO/packaging/deb/assemble-tree.sh" "$TREE"
rm -rf "$DEST"; mkdir -p "$DEST"
for image in adguard bind9 dirsrv freeradius kea keycloak stepca webui; do
    cp -a "$TREE/fabric/jinja/$image/build" "$DEST/$image"
done
cp -a "$TREE/fabric/lib/webui" "$DEST/webui/app"
echo "$DEST"
