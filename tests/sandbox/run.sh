#!/bin/bash
# -----------------------------------------------------------------------
# End-to-end install test in a disposable systemd + Docker sandbox:
#   fresh checkout -> sudo ./setup.sh --file vars.yaml --non-interactive --yes
#   -> fabricctl doctor -> fabricctl setup again (idempotent re-run)
#
#   sudo tests/sandbox/run.sh            (KEEP=1 leaves the sandbox running)
#
# The sandbox has its own Docker daemon, network and ports, so it does not
# touch the host's containers. Needs privileged Docker on the host.
# -----------------------------------------------------------------------
set -uo pipefail
exec 9>/tmp/fabric-sandbox-suite.lock
flock -n 9 || { echo "another sandbox run is active; refusing to start" >&2; exit 2; }
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="${FABRIC_TEST_OUT:-/tmp/fabric-tests}/sandbox"
NAME=fabric-sandbox
NET=fabric-sbx-net
SUBNET=10.77.0.0/24
IP=10.77.0.10
PASS=0; FAIL=0
check() { if eval "$2"; then echo "PASS $1"; PASS=$((PASS+1)); else echo "FAIL $1"; FAIL=$((FAIL+1)); fi; }
in_box() { docker exec "$NAME" bash -lc "$*"; }

docker rm -f "$NAME" >/dev/null 2>&1; docker network rm "$NET" >/dev/null 2>&1
docker volume rm fabric-sbx-docker >/dev/null 2>&1
rm -rf "$OUT"; mkdir -p "$OUT"

docker build -q -t fabric/sandbox:local "$REPO/tests/sandbox" >/dev/null || { echo "FAIL sandbox image"; exit 1; }
docker network create --subnet "$SUBNET" --gateway 10.77.0.1 "$NET" >/dev/null
# cgroupns=private and NO host /sys/fs/cgroup mount: the sandbox's systemd
# must never see the host's cgroup tree. With cgroupns=host its
# docker.service shared the host's cgroup, and restarting Docker inside the
# sandbox killed the host's dockerd.
docker run -d --name "$NAME" --hostname fabric-sbx --privileged --cgroupns=private \
  -v fabric-sbx-docker:/var/lib/docker \
  --tmpfs /run --tmpfs /run/lock --network "$NET" --ip "$IP" fabric/sandbox:local >/dev/null
for _ in $(seq 1 30); do in_box 'systemctl is-system-running 2>/dev/null' | grep -qE 'running|degraded' && break; sleep 2; done
# Nested Docker only: containerd's image store cannot unpack layers inside a
# container ("failed to convert whiteout file"); use the classic overlay2
# store. fabricctl merges its hardening into this file, so it survives.
in_box 'mkdir -p /etc/docker && echo "{\"features\": {\"containerd-snapshotter\": false}, \"storage-driver\": \"overlay2\"}" > /etc/docker/daemon.json'

# A clean checkout of the working tree (committed + uncommitted), like `git clone`.
(cd "$REPO" && git ls-files -z --cached --others --exclude-standard | tar --null -T - -cf "$OUT/src.tar")
docker exec "$NAME" mkdir -p /root/fabric
docker cp "$OUT/src.tar" "$NAME:/root/src.tar"
in_box 'tar -xf /root/src.tar -C /root/fabric && rm /root/src.tar'
cat > "$OUT/vars.yaml" <<EOF
domain: lan.test
hostname: fabric-sbx
host_ip: $IP
lan_cidr: $SUBNET
lan_gateway: 10.77.0.1
friendly_name: Sandbox
install_keycloak: true
install_ldap: true
install_webui: true
EOF
docker cp "$OUT/vars.yaml" "$NAME:/root/vars.yaml"

echo "--- setup (fresh install)"
in_box 'cd /root/fabric && ./setup.sh --file /root/vars.yaml --non-interactive --yes' 2>&1 | tee "$OUT/setup.log"
check "setup completes" "grep -q 'fabric is ready' '$OUT/setup.log'"

echo "--- doctor"
in_box 'fabricctl doctor' 2>&1 | tee "$OUT/doctor.log"
check "doctor: all checks pass" "! grep -q '✗' '$OUT/doctor.log' && grep -q '✓' '$OUT/doctor.log'"

echo "--- admin login kit"
check "kit: .p12, passwords and root CA in ~/fabric-admin" \
    "in_box 'cd /root/fabric-admin && ls fabricadmin.p12 p12-password.txt initial-password.txt README.txt *.crt' >/dev/null"
check "kit: secrets are 0600" \
    "[ \"\$(in_box 'stat -c %a /root/fabric-admin/fabricadmin.p12 /root/fabric-admin/p12-password.txt /root/fabric-admin/initial-password.txt' | sort -u)\" = 600 ]"

echo "--- real login: client cert -> web UI -> Keycloak (new password, TOTP) -> dashboard"
docker cp "$REPO/tests/sandbox/login_test.py" "$NAME:/root/login_test.py"
in_box 'python3 /root/login_test.py /opt/fabric/config/vars.yaml' 2>&1 | tee "$OUT/login.log"
check "real web UI login end to end" "! grep -q '^FAIL' '$OUT/login.log' && grep -q '^PASS dashboard' '$OUT/login.log'"

echo "--- setup again (must converge without changes)"
in_box 'fabricctl setup --non-interactive --yes' 2>&1 | tee "$OUT/setup2.log"
check "re-run completes" "grep -q 'fabric is ready' '$OUT/setup2.log'"
check "re-run re-issues no certificates" "! grep -q ': issued' '$OUT/setup2.log'"
check "re-run keeps the admin and their certificate" \
    "grep -q \"admin 'fabricadmin' exists\" '$OUT/setup2.log' && grep -q 'is current' '$OUT/setup2.log'"

echo "--- setup with a changed setting (live DNS zone must update, bind9 keeps serving)"
cat > "$OUT/change.yaml" <<EOF
dns:
  dynamic_zone_var:
    zone_authority: true
    A:
    - { name: rerun-test, ip: 10.77.0.99 }
EOF
docker cp "$OUT/change.yaml" "$NAME:/root/change.yaml"
in_box 'fabricctl setup --file /root/change.yaml --non-interactive --yes' > "$OUT/setup3.log" 2>&1
check "re-run with a change completes" "grep -q 'fabric is ready' '$OUT/setup3.log'"
check "new record served by the running bind9" \
    "in_box 'dig +short @$IP rerun-test.lan.test' | grep -qx 10.77.0.99"

cat > "$OUT/argv_check.py" <<'PY'
import glob, yaml
secrets = yaml.safe_load(open("/opt/fabric/config/fabric-secrets.yml"))
values = [v for v in secrets.values() if isinstance(v, str) and len(v) >= 12]
leaks = set()
for path in glob.glob("/proc/[0-9]*/cmdline"):
    try:
        argv = open(path, "rb").read().decode(errors="replace")
    except OSError:
        continue
    leaks.update(k for k, v in secrets.items() if isinstance(v, str) and len(v) >= 12 and v in argv)
print("LEAKS:", sorted(leaks) if leaks else "none")
PY
docker cp "$OUT/argv_check.py" "$NAME:/root/argv_check.py"
check "no secret appears in any process's argv" "in_box 'python3 /root/argv_check.py' | grep -q 'LEAKS: none'"

echo; echo "$PASS passed, $FAIL failed"
if [ "${KEEP:-0}" != 1 ]; then
    docker rm -f "$NAME" >/dev/null; docker network rm "$NET" >/dev/null; docker volume rm fabric-sbx-docker >/dev/null
fi
exit $FAIL
