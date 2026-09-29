#!/bin/bash
# -----------------------------------------------------------------------
# Run fabric's test suites against real containers.
#
#   sudo tests/run-all.sh [suite ...]      suites: render nginx zone webui pki openbao fluentbit kea dirsrv keycloak hardening
#   sudo tests/run-all.sh sandbox          opt-in: full install in a systemd + Docker sandbox (~10 min)
#
# Needs: Linux (amd64 or arm64), Docker with buildx, python3 with yaml +
# jinja2, openssl, curl, setpriv. Runs as root (chown to service uids,
# SO_PEERCRED checks). Output and scratch data: $FABRIC_TEST_OUT
# (default /tmp/fabric-tests). keycloak reuses the dirsrv suite's data.
# -----------------------------------------------------------------------
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
export FABRIC_TEST_OUT="${FABRIC_TEST_OUT:-/tmp/fabric-tests}"
SUITES=("$@")
[ ${#SUITES[@]} -eq 0 ] && SUITES=(render nginx zone webui pki openbao fluentbit kea dirsrv keycloak hardening)

[ "$(id -u)" -eq 0 ] || { echo "Run as root (sudo)." >&2; exit 2; }
rm -rf "$FABRIC_TEST_OUT"; mkdir -p "$FABRIC_TEST_OUT"
echo "fabric tests on $(uname -m), output in $FABRIC_TEST_OUT"

declare -A RESULT
run() {  # name command...
    local name="$1"; shift
    echo; echo "=== $name"
    local log="$FABRIC_TEST_OUT/$name.log"
    "$@" 2>&1 | tee "$log"
    local rc=${PIPESTATUS[0]}
    if [ "$rc" -eq 0 ] && ! grep -qE '^FAIL' "$log"; then RESULT[$name]=PASS; else RESULT[$name]=FAIL; fi
}

for s in "${SUITES[@]}"; do
    case "$s" in
        render)   run render   python3 "$HERE/render.py" "$FABRIC_TEST_OUT/rendered" ;;
        nginx)    run nginx    bash "$HERE/nginx_check.sh" "$FABRIC_TEST_OUT/rendered" ;;
        zone)     run zone     python3 "$HERE/zone_test.py" ;;
        webui)    run webui    bash -c "python3 \"$HERE/webui/test_container.py\" && python3 \"$HERE/webui/test_devserver.py\"" ;;
        pki)      run pki      python3 "$HERE/pki/run.py" ;;
        openbao)  run openbao  python3 "$HERE/openbao/run.py" ;;
        fluentbit) run fluentbit python3 "$HERE/fluentbit/run.py" ;;
        kea) run kea python3 "$HERE/kea/run.py" ;;
        dirsrv)   run dirsrv   bash "$HERE/dirsrv/run.sh" ;;
        keycloak) run keycloak bash "$HERE/keycloak/run.sh" ;;
        hardening) run hardening bash "$HERE/hardening/run.sh" ;;
        sandbox)  run sandbox  bash "$HERE/sandbox/run.sh" ;;
        *) echo "unknown suite: $s" >&2; exit 2 ;;
    esac
done

echo; echo "=== summary ($(uname -m))"
fail=0
for s in "${SUITES[@]}"; do
    printf '  %-9s %s\n' "$s" "${RESULT[$s]}"
    [ "${RESULT[$s]}" = PASS ] || fail=1
done
exit $fail
