#!/bin/bash
# -----------------------------------------------------------------------
# End-to-end test on a REAL host (e.g. a Raspberry Pi) over SSH, from the
# package, as users install it:
#   apt install ./fabricctl_<v>_all.deb -> fabricctl setup --file vars.yaml
#   -> doctor, fabric.target, certs.<domain> (HTTP + HTTPS), RFC2136 with an
#   embedded TSIG key, restricted sign-in (real Keycloak), re-run, stop/start.
#
#   TARGET=tempuser@192.168.4.57 HOST_IP=192.168.4.57 LAN_CIDR=192.168.4.0/22 \
#   GATEWAY=192.168.4.1 [DOMAIN=pitest.home.arpa] [KEY=~/.ssh/id] tests/host/run.sh
#
# It INSTALLS fabric on that host (Docker, firewall, services): use a
# disposable machine. The install is left in place; CLEANUP=1 uninstalls it.
# The SSH user needs key login and passwordless sudo.
# -----------------------------------------------------------------------
set -uo pipefail
: "${TARGET:?user@host}" "${HOST_IP:?}" "${LAN_CIDR:?}" "${GATEWAY:?}"
DOMAIN="${DOMAIN:-pitest.home.arpa}"
KEY="${KEY:-$HOME/.ssh/fabric-test_ed25519}"
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="${FABRIC_TEST_OUT:-/tmp/fabric-tests}/host"
SSH=(ssh -o BatchMode=yes -o ServerAliveInterval=30 -i "$KEY" "$TARGET")
PASS=0; FAIL=0
check() { if (set +o pipefail; eval "$2"); then echo "PASS $1"; PASS=$((PASS+1)); else echo "FAIL $1"; FAIL=$((FAIL+1)); fi; }
R() { "${SSH[@]}" "sudo bash -lc $(printf '%q' "$*")"; }          # run as root on the host
put() { scp -q -o BatchMode=yes -i "$KEY" "$1" "$TARGET:/tmp/$(basename "$1")"; }
rm -rf "$OUT"; mkdir -p "$OUT"

LOGIN=$("${SSH[@]}" whoami); HOSTNAME_=$("${SSH[@]}" 'hostname -s')
echo "--- target: $TARGET ($("${SSH[@]}" 'uname -m; . /etc/os-release; echo $PRETTY_NAME' | tr '\n' ' '))"

DEB=$(OUT="$OUT/dist" bash "$REPO/packaging/build-deb.sh") || { echo "FAIL package build"; exit 1; }
put "$DEB"
R "apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq /tmp/$(basename "$DEB")" > "$OUT/apt.log" 2>&1
check "package installs with apt on the host" "R 'dpkg -s fabricctl' | grep -q '^Status: install ok installed'"

TSIG_SECRET=$(openssl rand -base64 32)
cat > "$OUT/vars.yaml" <<EOF
domain: $DOMAIN
hostname: $HOSTNAME_
host_ip: $HOST_IP
lan_cidr: $LAN_CIDR
lan_gateway: $GATEWAY
friendly_name: Fabric host test
install_keycloak: true
install_ldap: true
install_webui: true
tsig_keys:
- { name: npm, records: [npm], secret: "$TSIG_SECRET", acls: [npm-updaters] }
EOF
put "$OUT/vars.yaml"

echo "--- setup (this host builds its images; takes a while on a Pi)"
start=$(date +%s)
R "fabricctl setup --file /tmp/vars.yaml --non-interactive --yes" > "$OUT/setup.log" 2>&1
echo "    setup took $(( ($(date +%s) - start) / 60 )) min"
check "setup completes" "grep -q 'fabric is ready' '$OUT/setup.log'"
R 'fabricctl doctor' > "$OUT/doctor.log" 2>&1
check "doctor: all checks pass" "! grep -q '✗' '$OUT/doctor.log' && grep -q '✓' '$OUT/doctor.log'"
check "fabric.target enabled and active" "R 'systemctl is-enabled fabric.target && systemctl is-active fabric.target' >/dev/null"
R 'fabricctl status' > "$OUT/status.log" 2>&1
check "every container healthy" "[ \"\$(grep -c ' healthy' '$OUT/status.log')\" -ge 7 ]"

NGINX_IP=$(R "python3 -c 'import yaml;print(yaml.safe_load(open(\"/opt/fabric/config/vars.yaml\"))[\"ip_nginx\"])'")
for f in certs_page_test.sh rfc2136_test.sh login_test.py; do put "$REPO/tests/sandbox/$f"; done
R "bash /tmp/certs_page_test.sh certs.$DOMAIN ca.$DOMAIN $NGINX_IP $HOST_IP" > "$OUT/certs-page.log" 2>&1
check "certs page: formats, CA identity, MIME, plain HTTP by name and IP, ca.<domain> = Step-CA" \
    "! grep -q '^FAIL' '$OUT/certs-page.log' && [ \"\$(grep -c '^PASS' '$OUT/certs-page.log')\" -ge 18 ]"
check "LAN clients reach the certificate page over plain HTTP: http://$HOST_IP/certs/" \
    "curl -s --max-time 10 http://$HOST_IP/certs/root-ca.pem | grep -q 'BEGIN CERTIFICATE'"

R "bash /tmp/rfc2136_test.sh $HOST_IP $DOMAIN npm '$TSIG_SECRET' npm" > "$OUT/rfc2136.log" 2>&1
check "RFC2136 with the embedded TSIG key (npm): allowed name only, wrong keys refused" "grep -q '4 passed, 0 failed' '$OUT/rfc2136.log'"

echo "--- restricted sign-in (real Keycloak)"
BOB_PW=$(openssl rand -base64 18)
cat > "$OUT/bob.py" <<'PY'
import os, sys, yaml
sys.path.insert(0, "/opt/fabric/lib")
from fabriclib.ldap.ensure_admin_user import ensure_admin_user
v = yaml.safe_load(open("/opt/fabric/config/vars.yaml"))
print(ensure_admin_user(dict(v, webui_admin_group="users"), "bob", os.environ["BOB_PW"], "bob@example.invalid"))
PY
put "$OUT/bob.py"
R "BOB_PW='$BOB_PW' python3 /tmp/bob.py" > "$OUT/bob.log" 2>&1
BOB_P12_PW=$(R 'fabricctl client-cert bob' 2>&1 | sed -n 's/^.p12 password (shown once): //p')
KIT=$(R "getent passwd $LOGIN | cut -d: -f6")/fabric-admin
# A host signed into before (this suite re-run on the same machine): put the admin and
# bob back to their first-login state, so the scripted sign-in sees the same flow.
put "$REPO/tests/host/reset_user.py"
ADMIN=$(R "awk '/^webui_admin_user:/{print \$2}' /opt/fabric/config/vars.yaml")
R "PW=\$(cat $KIT/initial-password.txt) python3 /tmp/reset_user.py $ADMIN" > "$OUT/reset.log" 2>&1
R "PW='$BOB_PW' python3 /tmp/reset_user.py bob" >> "$OUT/reset.log" 2>&1
R "FABRIC_KIT=$KIT NEW_PERSON=dave$(date +%s) python3 /tmp/login_test.py /opt/fabric/config/vars.yaml bob '$BOB_PW' '$BOB_P12_PW'" > "$OUT/login.log" 2>&1
check "sign-in: admin in; HTTP, missing/foreign certs, non-admin and borrowed certs refused" \
    "! grep -q '^FAIL' '$OUT/login.log' && [ \"\$(grep -c '^PASS' '$OUT/login.log')\" -ge 11 ]"
check "login kit in the admin's home ($KIT), secrets 0600" \
    "[ \"\$(R 'stat -c %a $KIT/p12-password.txt $KIT/initial-password.txt' | sort -u)\" = 600 ]"

echo "--- re-run and restart"
R 'fabricctl setup --non-interactive --yes' > "$OUT/setup2.log" 2>&1
check "setup re-run converges (no certificate re-issued)" "grep -q 'fabric is ready' '$OUT/setup2.log' && ! grep -q ': issued' '$OUT/setup2.log'"
R 'fabricctl stop' > /dev/null 2>&1
check "fabricctl stop: DNS goes quiet" "! R 'dig +time=2 +tries=1 +short @$HOST_IP ns.$DOMAIN' | grep -qx $HOST_IP"
R 'fabricctl start' > /dev/null 2>&1
R 'fabricctl doctor' > "$OUT/doctor2.log" 2>&1
check "fabricctl start: back, doctor passes" "! grep -q '✗' '$OUT/doctor2.log' && grep -q '✓' '$OUT/doctor2.log'"

cat > "$OUT/argv_check.py" <<'PY'
import glob, sys
sys.path.insert(0, "/opt/fabric/lib")
from fabriclib.secrets.load_secrets import load_secrets   # the file, or OpenBao once imported
secrets = load_secrets("/opt/fabric/config/fabric-secrets.yml")
leaks = set()
for path in glob.glob("/proc/[0-9]*/cmdline"):
    try:
        argv = open(path, "rb").read().decode(errors="replace")
    except OSError:
        continue
    leaks.update(k for k, v in secrets.items() if isinstance(v, str) and len(v) >= 12 and v in argv)
print("LEAKS:", sorted(leaks) if leaks else "none")
PY
put "$OUT/argv_check.py"
check "no secret in any process's argv" "R 'python3 /tmp/argv_check.py' | grep -q 'LEAKS: none'"

if [ "${CLEANUP:-0}" = 1 ]; then
    # apt purge: apt cannot ask, so fabric's data is exported to /var/backups/fabric/ first
    R 'DEBIAN_FRONTEND=noninteractive apt-get purge -y -q fabricctl' > "$OUT/uninstall.log" 2>&1
    check "apt purge: data exported to /var/backups/fabric, fabric removed"         "R 'ls -d /var/backups/fabric/fabric-export-*/stepca/data' >/dev/null 2>&1 && ! R 'test -e /opt/fabric' && ! R 'dpkg -s fabricctl' >/dev/null 2>&1"
fi
echo; echo "$PASS passed, $FAIL failed   (logs: $OUT)"
exit $FAIL
