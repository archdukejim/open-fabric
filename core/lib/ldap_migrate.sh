#!/bin/bash
# -----------------------------------------------------------------------
# ldap_migrate.sh — one-time move of users/groups from the old osixia
# OpenLDAP data directory into the running 389 Directory Server.
#
#   sudo bash /opt/core/lib/ldap_migrate.sh [old_dir] [old_image]
#     old_dir    default: <deploy_base>/openldap
#     old_image  default: osixia/openldap:1.5.0  (only used to run slapcat)
#
# Steps: slapcat the old data (from a copy), export the current 389-DS
# backend (kept as a backup in /opt/dirsrv/data/ldif), merge, then import
# the merged LDIF. Import — unlike LDAP adds — keeps entryUUID, which
# Keycloak uses to link federated users. Safe to re-run: when nothing new
# is found no import happens. Delete the old directory yourself once
# logins through 389-DS and Keycloak are verified.
# -----------------------------------------------------------------------
set -euo pipefail

actual_script=$(readlink -f "${BASH_SOURCE[0]}")
LIB_DIR="$(dirname "$actual_script")"
DEPLOY_BASE="$(dirname "$(dirname "$LIB_DIR")")"
OLD_DIR="${1:-${DEPLOY_BASE}/openldap}"
OLD_IMAGE="${2:-osixia/openldap:1.5.0}"
DS=dirsrv

source "$LIB_DIR/dirsrv.sh"

[ "$(id -u)" -eq 0 ] || { echo "Run as root." >&2; exit 1; }
[ -d "$OLD_DIR/data" ] && [ -d "$OLD_DIR/config" ] || {
    echo "No OpenLDAP data found in $OLD_DIR (expected data/ and config/)." >&2; exit 1; }

dirsrv_wait_healthy

stamp=$(date -u +%Y%m%d-%H%M%S)
work=$(mktemp -d)
trap 'rm -rf "$work"; docker exec -u 0 "$DS" rm -f /tmp/openldap-export.ldif 2>/dev/null || true' EXIT
chmod 700 "$work"

echo "[1/5] Exporting OpenLDAP database (read-only copy of $OLD_DIR)..."
cp -a "$OLD_DIR/data" "$work/data"
cp -a "$OLD_DIR/config" "$work/config"
docker run --rm --network none --user 0 \
    -v "$work/data:/var/lib/ldap" -v "$work/config:/etc/ldap/slapd.d" \
    --entrypoint slapcat "$OLD_IMAGE" -n 1 -o ldif-wrap=no > "$work/export.ldif"
echo "      $(grep -c '^dn:' "$work/export.ldif") entries exported"
docker cp "$work/export.ldif" "$DS:/tmp/openldap-export.ldif"

echo "[2/5] Backing up the current 389-DS database..."
backup="/data/ldif/pre-migrate-${stamp}.ldif"
docker exec "$DS" dsconf localhost backend export userroot -l "$backup" >/dev/null
echo "      $backup (inside the container; $DEPLOY_BASE/dirsrv/data/ldif on the host)"

echo "[3/5] Merging..."
merged="/data/ldif/migrated-${stamp}.ldif"
out=$(docker exec -i "$DS" python3 - /tmp/openldap-export.ldif "$backup" "$merged" < "$LIB_DIR/ldap_migrate.py")
echo "      $out" | head -1
if grep -q NOTHING_TO_IMPORT <<<"$out"; then
    echo "      Nothing new to import."
else
    echo "[4/5] Importing merged LDIF (entryUUIDs preserved)..."
    docker exec "$DS" dsconf localhost backend import userroot "$merged" >/dev/null
    docker exec "$DS" dsconf localhost plugin memberof fixup "$(docker exec "$DS" sh -c 'echo "$DS_SUFFIX_NAME"')" >/dev/null
fi

echo "[5/5] Re-syncing Keycloak federation (if installed)..."
if systemctl is-active --quiet keycloak; then
    python3 "$LIB_DIR/keycloak_bootstrap.py" \
        --vars "$DEPLOY_BASE/core/config/vars.yaml" \
        --secrets "$DEPLOY_BASE/core/config/core-secrets.yml"
fi
echo "Done. Verify a user login, then remove $OLD_DIR when satisfied."
