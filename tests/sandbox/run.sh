#!/bin/bash
# -----------------------------------------------------------------------
# End-to-end test of the product as users get it, in a disposable
# systemd + Docker sandbox (Ubuntu 24.04, no git checkout inside):
#   apt install ./fabricctl_<v>_all.deb -> fabricctl setup --file vars.yaml
#   -> doctor, systemd control (fabric.target), real sign-in incl. refusals,
#   RFC2136/TSIG/ACLs, re-runs, package upgrade, apt remove
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
# Checks run without pipefail: `cmd | grep -q x` must not fail when grep
# finds x early and cmd then gets SIGPIPE writing the rest of its output.
check() { if (set +o pipefail; eval "$2"); then echo "PASS $1"; PASS=$((PASS+1)); else echo "FAIL $1"; FAIL=$((FAIL+1)); fi; }
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

# The package, built from the working tree exactly as a release would be.
DEB=$(OUT="$OUT/dist" bash "$REPO/packaging/build-deb.sh") || { echo "FAIL package build"; exit 1; }
docker cp "$DEB" "$NAME:/root/fabricctl.deb"
echo "--- apt install ./$(basename "$DEB")"
in_box 'apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq /root/fabricctl.deb' > "$OUT/apt.log" 2>&1
check "package installs with apt (dependencies resolved)" "in_box 'dpkg -s fabricctl' | grep -q '^Status: install ok installed'"
check "fabricctl is the packaged command" "in_box 'command -v fabricctl' | grep -qx /usr/bin/fabricctl"
check "installing the package started nothing" "! in_box 'test -e /etc/systemd/system/fabric.target'"
# (the command exits 1 here by design; `; true` keeps pipefail from masking grep)
check "before setup, day-2 commands say what to do" "in_box 'fabricctl status 2>&1; true' | grep -q 'not set up on this host yet'"
# An existing TSIG key (as on a host being rebuilt) whose RFC2136 client —
# nginx-proxy-manager's certbot plugin — must keep working unchanged.
TSIG_SECRET=$(openssl rand -base64 32)
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
tsig_keys:
- { name: npm, records: [npm], secret: "$TSIG_SECRET", acls: [npm-updaters] }
EOF
docker cp "$OUT/vars.yaml" "$NAME:/root/vars.yaml"

echo "--- setup (fresh install)"
in_box 'fabricctl setup --file /root/vars.yaml --non-interactive --yes' 2>&1 | tee "$OUT/setup.log"
check "setup completes" "grep -q 'fabric is ready' '$OUT/setup.log'"
check "setup did not shadow the package command" "! in_box 'test -e /usr/local/bin/fabricctl'"

echo "--- doctor"
in_box 'fabricctl doctor' 2>&1 | tee "$OUT/doctor.log"
check "doctor: all checks pass" "! grep -q '✗' '$OUT/doctor.log' && grep -q '✓' '$OUT/doctor.log'"

echo "--- systemd control: fabric.target"
check "fabric.target enabled and active" "in_box 'systemctl is-enabled fabric.target && systemctl is-active fabric.target' >/dev/null"
check "every unit is part of fabric.target" \
    "[ \"\$(in_box 'systemctl list-dependencies --plain fabric.target' | grep -cE '(bind9|stepca|nginx|ldap|postgres|keycloak|fabric-agent|webui)\\.service')\" -ge 8 ]"
in_box 'fabricctl status' > "$OUT/status.log" 2>&1
check "fabricctl status: target active, containers healthy" \
    "grep -qE '^fabric.target +active' '$OUT/status.log' && [ \"\$(grep -c ' healthy' '$OUT/status.log')\" -ge 7 ]"
in_box 'fabricctl stop' > "$OUT/stop.log" 2>&1
check "fabricctl stop: every service stopped" \
    "! in_box 'systemctl is-active bind9 stepca nginx ldap postgres keycloak webui fabric-agent' | grep -qx active"
check "fabricctl stop: DNS no longer answers" "! in_box 'dig +time=2 +tries=1 +short @$IP ns.lan.test' | grep -qx $IP"
in_box 'fabricctl start' > "$OUT/start.log" 2>&1
sleep 20
in_box 'fabricctl doctor' > "$OUT/doctor-after-start.log" 2>&1
check "fabricctl start: everything back, doctor passes" \
    "! grep -q '✗' '$OUT/doctor-after-start.log' && grep -q '✓' '$OUT/doctor-after-start.log'"
in_box 'systemctl restart fabric.target' > /dev/null 2>&1
sleep 20
in_box 'fabricctl doctor' > "$OUT/doctor-after-restart.log" 2>&1
check "systemctl restart fabric.target: doctor passes" \
    "! grep -q '✗' '$OUT/doctor-after-restart.log' && grep -q '✓' '$OUT/doctor-after-restart.log'"

echo "--- RFC2136 with the embedded TSIG key (what nginx-proxy-manager does)"
docker cp "$REPO/tests/sandbox/rfc2136_test.sh" "$NAME:/root/rfc2136_test.sh"
rfc2136() { in_box "bash /root/rfc2136_test.sh $IP lan.test npm '$TSIG_SECRET' npm" 2>&1 | tee -a "$OUT/rfc2136.log"; }
rfc2136 > /dev/null
check "RFC2136: embedded key updates _acme-challenge.npm, other names and wrong keys refused" \
    "grep -q '4 passed, 0 failed' '$OUT/rfc2136.log'"
check "embedded secret kept exactly, and only in fabric-secrets.yml" \
    "in_box \"grep -qF '$TSIG_SECRET' /opt/fabric/config/fabric-secrets.yml && ! grep -qF '$TSIG_SECRET' /opt/fabric/config/vars.yaml /opt/fabric/config/fabric.yaml\""
check "rfc2136.ini for the key: host IP, port 53, 0600" \
    "in_box \"grep -qx 'dns_rfc2136_server = $IP' /opt/npm/rfc2136.ini && grep -qx 'dns_rfc2136_port = 53' /opt/npm/rfc2136.ini && [ \\\$(stat -c %a /opt/npm/rfc2136.ini) = 600 ]\""

echo "--- admin login kit"
check "kit: .p12, passwords and root CA in ~/fabric-admin" \
    "in_box 'cd /root/fabric-admin && ls fabricadmin.p12 p12-password.txt initial-password.txt README.txt *.crt' >/dev/null"
check "kit: secrets are 0600" \
    "[ \"\$(in_box 'stat -c %a /root/fabric-admin/fabricadmin.p12 /root/fabric-admin/p12-password.txt /root/fabric-admin/initial-password.txt' | sort -u)\" = 600 ]"

echo "--- restricted sign-in: HTTPS + client cert from this CA + Keycloak OIDC/TOTP + fabric-admin role"
# A real directory user who is NOT in admins, with their own valid client certificate.
BOB_PW=$(openssl rand -base64 18)
cat > "$OUT/bob.py" <<'PY'
import os, sys, yaml
sys.path.insert(0, "/opt/fabric/lib")
from fabriclib.ldap.ensure_admin_user import ensure_admin_user
v = yaml.safe_load(open("/opt/fabric/config/vars.yaml"))
print(ensure_admin_user(dict(v, webui_admin_group="users"), "bob", os.environ["BOB_PW"], "bob@lan.test"))
PY
docker cp "$OUT/bob.py" "$NAME:/root/bob.py"
in_box "BOB_PW='$BOB_PW' python3 /root/bob.py" > "$OUT/bob.log" 2>&1
BOB_P12_PW=$(in_box 'fabricctl client-cert bob' 2>&1 | sed -n 's/^.p12 password (shown once): //p')
check "second user bob (directory user, not an admin) with a client cert" "grep -q created '$OUT/bob.log' && [ -n '$BOB_P12_PW' ]"
docker cp "$REPO/tests/sandbox/login_test.py" "$NAME:/root/login_test.py"
in_box "python3 /root/login_test.py /opt/fabric/config/vars.yaml bob '$BOB_PW' '$BOB_P12_PW'" 2>&1 | tee "$OUT/login.log"
check "sign-in: admin gets in; HTTP, missing/foreign certs, non-admins and borrowed certs are refused" \
    "! grep -q '^FAIL' '$OUT/login.log' && [ \"\$(grep -c '^PASS' '$OUT/login.log')\" -ge 11 ]"

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
: > "$OUT/rfc2136.log"; rfc2136 > /dev/null
check "RFC2136 key still works after the re-runs (secret unchanged)" "grep -q '4 passed, 0 failed' '$OUT/rfc2136.log'"

echo "--- fabricctl tsig / acl on the running install"
ACLF=/opt/bind9/config/named.conf.acl
t2136() { in_box "bash /root/rfc2136_test.sh $IP lan.test $1 '$2' $3" 2>&1 | tail -1; }   # key secret host
secret_of() { in_box "python3 -c \"import yaml;print(yaml.safe_load(open('/opt/fabric/config/fabric-secrets.yml'))['tsig_secrets']['$1'])\""; }
check "vars file: npm key is in ACL npm-updaters" \
    "in_box \"sed -n '/acl \\\"npm-updaters\\\"/,/};/p' $ACLF\" | grep -q 'key \"npm\"'"

S2=$(openssl rand -base64 32)
in_box "umask 077; printf '%s' '$S2' > /root/nas.secret"
in_box 'fabricctl tsig add nas --record nas --secret-file /root/nas.secret --acl nas-updaters' > "$OUT/tsig.log" 2>&1
check "tsig add: existing secret kept, key in ACL nas-updaters" \
    "grep -q \"TSIG key 'nas' added (existing secret kept), in ACL nas-updaters.\" '$OUT/tsig.log'"
check "tsig add: key works over RFC2136" "[ \"\$(t2136 nas '$S2' nas)\" = '4 passed, 0 failed' ]"
check "tsig add: ACL rendered with the key" "in_box \"sed -n '/acl \\\"nas-updaters\\\"/,/};/p' $ACLF\" | grep -q 'key \"nas\"'"

in_box 'fabricctl tsig rotate nas' >> "$OUT/tsig.log" 2>&1
S3=$(secret_of nas)
check "tsig rotate: old secret refused" "[ \"\$(t2136 nas '$S2' nas | cut -d' ' -f1)\" != 4 ]"
check "tsig rotate: new secret works" "[ -n '$S3' ] && [ '$S3' != '$S2' ] && [ \"\$(t2136 nas '$S3' nas)\" = '4 passed, 0 failed' ]"
check "tsig rotate: rfc2136.ini carries the new secret" "in_box \"grep -qxF 'dns_rfc2136_secret = $S3' /opt/nas/rfc2136.ini\""

in_box 'fabricctl tsig set-secret nas --secret-file /root/nas.secret' >> "$OUT/tsig.log" 2>&1
check "tsig set-secret: the given secret works again" "[ \"\$(t2136 nas '$S2' nas)\" = '4 passed, 0 failed' ]"

in_box 'fabricctl tsig update nas --record web' >> "$OUT/tsig.log" 2>&1
check "tsig update: new record allowed" "[ \"\$(t2136 nas '$S2' web)\" = '4 passed, 0 failed' ]"
check "tsig update: old record no longer allowed" "[ \"\$(t2136 nas '$S2' nas | cut -d' ' -f1)\" != 4 ]"

in_box "fabricctl acl add lab 192.168.50.0/24 10.9.9.9 'key nas'" >> "$OUT/tsig.log" 2>&1
check "acl add: rendered with CIDR, IP and key" \
    "in_box \"sed -n '/acl \\\"lab\\\"/,/};/p' $ACLF\" | tr -d ' ' | grep -c -e '192.168.50.0/24;' -e '10.9.9.9;' -e 'key\"nas\";' | grep -qx 3"
check "acl add: rejects nonsense" "! in_box \"fabricctl acl add lab 'not-an-ip'\" >/dev/null 2>&1"
check "acl remove: built-in ACL protected" "! in_box 'fabricctl acl remove dns-resolvers' >/dev/null 2>&1"
in_box 'fabricctl acl remove lab 10.9.9.9' >> "$OUT/tsig.log" 2>&1
check "acl remove: one entry" "! in_box \"grep -q '10.9.9.9' $ACLF\""

echo "--- ACL policy: only certbot devices in the ACL may prove names for certificates"
D1=$(openssl rand -base64 32); D2=$(openssl rand -base64 32)
in_box "umask 077; printf '%s' '$D1' > /root/d1.secret; printf '%s' '$D2' > /root/d2.secret"
in_box 'fabricctl acl policy certbot-devices --record web' >> "$OUT/tsig.log" 2>&1
in_box 'fabricctl tsig add dev1 --acl certbot-devices --secret-file /root/d1.secret' >> "$OUT/tsig.log" 2>&1
in_box 'fabricctl tsig add dev2 --secret-file /root/d2.secret' >> "$OUT/tsig.log" 2>&1
check "policy: device key in the ACL may set _acme-challenge.web (other names refused)" \
    "[ \"\$(t2136 dev1 '$D1' web)\" = '4 passed, 0 failed' ]"
check "policy: a key outside the ACL has no update rights (deny by default)" \
    "[ \"\$(t2136 dev2 '$D2' web | cut -d' ' -f1)\" != 4 ]"
check "policy: tsig list shows rights via the ACL and none for the other key" \
    "in_box 'fabricctl tsig list' | grep -A1 '^dev1' | grep -q 'via ACL certbot-devices' && in_box 'fabricctl tsig list' | grep '^dev2' | grep -q 'no update rights'"
in_box 'fabricctl acl policy certbot-devices --record web --record git' >> "$OUT/tsig.log" 2>&1
check "policy: widened to git, members follow" "[ \"\$(t2136 dev1 '$D1' git)\" = '4 passed, 0 failed' ]"
in_box 'fabricctl tsig update dev1 --drop-acl certbot-devices' >> "$OUT/tsig.log" 2>&1
check "policy: key taken out of the ACL loses the rights" "[ \"\$(t2136 dev1 '$D1' web | cut -d' ' -f1)\" != 4 ]"
in_box 'fabricctl tsig update dev1 --acl certbot-devices' >> "$OUT/tsig.log" 2>&1
in_box 'fabricctl acl policy certbot-devices --clear' >> "$OUT/tsig.log" 2>&1
check "policy cleared: members lose the rights" "[ \"\$(t2136 dev1 '$D1' web | cut -d' ' -f1)\" != 4 ]"
in_box 'fabricctl tsig remove dev1 && fabricctl tsig remove dev2 && fabricctl acl remove certbot-devices' >> "$OUT/tsig.log" 2>&1
check "policy: cleanup leaves no trace in BIND's config" \
    "! in_box \"grep -rqE 'dev1|dev2|certbot-devices' /opt/bind9/config\""

in_box 'fabricctl tsig remove nas' >> "$OUT/tsig.log" 2>&1
in_box "bash /root/rfc2136_test.sh $IP lan.test nas '$S2' web" > "$OUT/tsig-removed.log" 2>&1
check "tsig remove: key refused by BIND" "grep -q '^FAIL RFC2136 update with the embedded key accepted' '$OUT/tsig-removed.log'"
check "tsig remove: key gone from every ACL" "! in_box \"grep -q 'key \\\"nas\\\"' $ACLF\""
check "tsig remove: rfc2136.ini deleted" "! in_box 'test -e /opt/nas/rfc2136.ini'"
check "BIND still serves after all changes" "in_box 'dig +short @$IP ns.lan.test' | grep -qx $IP"
check "the npm key is unaffected" "[ \"\$(t2136 npm '$TSIG_SECRET' npm)\" = '4 passed, 0 failed' ]"

echo "--- package upgrade and removal"
sleep 2    # a later build timestamp = a newer package version
DEB2=$(OUT="$OUT/dist2" bash "$REPO/packaging/build-deb.sh")
docker cp "$DEB2" "$NAME:/root/fabricctl-new.deb"
in_box 'DEBIAN_FRONTEND=noninteractive apt-get install -y -qq /root/fabricctl-new.deb' > "$OUT/apt2.log" 2>&1
check "newer package installs over the old one" "grep -q 'package updated' '$OUT/apt2.log'"
check "until setup runs, commands say the package is newer" "in_box 'fabricctl status' 2>&1 | grep -q 'package is newer'"
in_box 'fabricctl setup --non-interactive --yes' > "$OUT/setup-upgrade.log" 2>&1
check "setup applies the upgrade" "grep -q 'fabric is ready' '$OUT/setup-upgrade.log' && ! in_box 'fabricctl status' 2>&1 | grep -q 'package is newer'"
check "the install runs the upgraded build" "in_box 'cmp /usr/lib/fabricctl/fabric/BUILD /opt/fabric/BUILD'"
in_box 'DEBIAN_FRONTEND=noninteractive apt-get remove -y -qq fabricctl' > "$OUT/apt-remove.log" 2>&1
check "apt remove removes the command but not the running install" \
    "! in_box 'test -e /usr/bin/fabricctl' && in_box 'systemctl is-active fabric.target' | grep -qx active && in_box 'dig +short @$IP ns.lan.test' | grep -qx $IP"
in_box 'DEBIAN_FRONTEND=noninteractive apt-get install -y -qq /root/fabricctl-new.deb' > /dev/null 2>&1
check "reinstalling the package gives the command back" "in_box 'fabricctl status' | grep -qE '^fabric.target +active'"

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
