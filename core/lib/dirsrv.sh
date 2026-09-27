#!/bin/bash
# 389 Directory Server helpers — source this file, do not execute directly.
# Also callable directly: bash dirsrv.sh seed

# -----------------------------------------------------------------------
# dirsrv_wait_healthy [timeout_seconds]
# -----------------------------------------------------------------------
dirsrv_wait_healthy() {
    local timeout="${1:-300}" waited=0 status
    while [ "$waited" -lt "$timeout" ]; do
        status=$(docker inspect -f '{{.State.Health.Status}}' dirsrv 2>/dev/null || echo missing)
        [ "$status" = "healthy" ] && return 0
        sleep 5; waited=$((waited + 5))
    done
    echo "dirsrv did not become healthy within ${timeout}s (last status: ${status})" >&2
    return 1
}

# -----------------------------------------------------------------------
# dirsrv_seed
# Apply /seed/*.ldif idempotently inside the container and restart the
# ldap service once if server configuration (cn=config) changed.
# -----------------------------------------------------------------------
dirsrv_seed() {
    dirsrv_wait_healthy || return 1
    local out
    # dscontainer only records DS_SUFFIX_NAME in .dsrc; create the backend on first run.
    docker exec dirsrv sh -c 'dsconf localhost backend suffix list 2>/dev/null | grep -qiF "$DS_SUFFIX_NAME (" \
        || dsconf localhost backend create --suffix "$DS_SUFFIX_NAME" --be-name userroot' || return 1
    out=$(docker exec dirsrv sh -c 'python3 /seed/seed.py /seed/*.ldif') || { echo "$out" >&2; return 1; }
    echo "$out"
    if grep -q '^RESTART_REQUIRED$' <<<"$out"; then
        echo "389-DS configuration changed — restarting ldap service..."
        systemctl restart ldap
        dirsrv_wait_healthy
    fi
}

if [ "${BASH_SOURCE[0]}" = "$0" ] && [ "${1:-}" = "seed" ]; then
    set -euo pipefail
    dirsrv_seed
fi
