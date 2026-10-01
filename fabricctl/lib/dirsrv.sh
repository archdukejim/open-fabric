#!/bin/bash
# 389 Directory Server helpers — source this file, do not execute directly.
# Also callable directly: bash dirsrv.sh seed

# -----------------------------------------------------------------------
# Purpose: wait until the dirsrv container's Docker healthcheck reports "healthy".
# Inputs:  $1 — timeout in seconds (optional, default 300); polls `docker inspect` every 5 s.
# Returns: exit status 0 as soon as it is healthy.
# Fails:   status 1 after the timeout, with "dirsrv did not become healthy within Ns (last status: ...)"
#          on stderr (status "missing" if the container does not exist).
# Feeds:   dirsrv_seed (before seeding and again after a restart).
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
# Purpose: seed 389-DS: create the two suffix backends (organisation, local) on first run, apply /seed/*.ldif
#          idempotently inside the container (seed.py) and restart the ldap service once if server configuration
#          (cn=config) changed.
# Inputs:  none; needs the running dirsrv container with DS_SUFFIX_NAME and DS_LOCAL_SUFFIX set and the rendered seed files
#          (deploy.py copies them to <base>/dirsrv/seed, mounted at /seed).
# Returns: seed.py's output on stdout (plus a restart notice when it printed RESTART_REQUIRED); the exit status of
#          the final dirsrv_wait_healthy after a restart, else 0.
# Fails:   status 1 if dirsrv never becomes healthy, if the backend cannot be created after 12 tries (5 s apart,
#          "389-DS backend could not be created" on stderr), or if seed.py fails (its output on stderr).
# Feeds:   `bash dirsrv.sh seed`, run by apply_deployment (deploy.py) when seed files changed and by
#          fabriclib/setup/start_services.py; tests/dirsrv/run.sh mirrors the same steps.
dirsrv_seed() {
    dirsrv_wait_healthy || return 1
    local out
    # dscontainer only records DS_SUFFIX_NAME in .dsrc; create the backends on first run: the organisation
    # suffix (people, groups, device roles) and this install's local suffix (its service accounts and devices).
    # The healthcheck can pass a moment before LDAPI accepts connections: retry.
    local tries=0
    until docker exec dirsrv sh -c 'dsconf localhost backend suffix list 2>/dev/null | grep -qiF "$DS_SUFFIX_NAME (" \
            || dsconf localhost backend create --suffix "$DS_SUFFIX_NAME" --be-name userroot' \
          && docker exec dirsrv sh -c 'dsconf localhost backend suffix list 2>/dev/null | grep -qiF "$DS_LOCAL_SUFFIX (" \
            || dsconf localhost backend create --suffix "$DS_LOCAL_SUFFIX" --be-name sitelocal --parent-suffix "$DS_SUFFIX_NAME"'; do
        tries=$((tries + 1))
        [ "$tries" -ge 12 ] && { echo "389-DS backend could not be created" >&2; return 1; }
        sleep 5
    done
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
