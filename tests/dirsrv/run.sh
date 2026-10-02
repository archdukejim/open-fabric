#!/bin/bash
# 389-DS integration test: real image, compose-equivalent hardening, our seed
# data (rendered by tests/render.py into $FABRIC_TEST_OUT/rendered), TLS and the first-admin user.
set -uo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="${FABRIC_TEST_OUT:-/tmp/fabric-tests}"
W=$OUT/dirsrv
BASE="dc=lan,dc=j-j,dc=family"
LOCAL="ou=pi-core,$BASE"     # the site part, a sub-suffix (tests/render.py's host name)
DM_PW='DmPass1'
PASS=0; FAIL=0
check() { if eval "$2"; then echo "PASS $1"; PASS=$((PASS+1)); else echo "FAIL $1"; FAIL=$((FAIL+1)); fi; }

docker rm -f dstest >/dev/null 2>&1
docker build -q --build-arg BASE_IMAGE="$(python3 "$REPO/tests/image_ref.py" debian)" --build-arg DS_UID=911 --build-arg DS_GID=911 -t fabric/dirsrv:test "$REPO/fabricctl/jinja/dirsrv/build" >/dev/null || { echo "FAIL image build"; exit 1; }
rm -rf "$W"; mkdir -p "$W/data/tls/ca" "$W/seed"
cd "$W"

# ---- PKI: root -> intermediate -> ldap.lan.j-j.family
openssl req -x509 -newkey rsa:2048 -nodes -keyout root.key -out root.crt -days 2 -subj '/CN=Test Root' \
  -addext basicConstraints=critical,CA:TRUE -addext keyUsage=critical,keyCertSign,cRLSign 2>/dev/null
openssl req -newkey rsa:2048 -nodes -keyout int.key -out int.csr -subj '/CN=Test Int' 2>/dev/null
printf 'basicConstraints=critical,CA:TRUE,pathlen:0\nkeyUsage=critical,keyCertSign,cRLSign\n' > int.ext
openssl x509 -req -in int.csr -CA root.crt -CAkey root.key -CAcreateserial -out int.crt -days 2 -extfile int.ext 2>/dev/null
openssl req -newkey rsa:2048 -nodes -keyout ldap.key -out ldap.csr -subj '/CN=ldap.lan.j-j.family' 2>/dev/null
printf 'subjectAltName=DNS:ldap.lan.j-j.family\nextendedKeyUsage=serverAuth,clientAuth\n' > ldap.ext
openssl x509 -req -in ldap.csr -CA int.crt -CAkey int.key -CAcreateserial -out ldap.crt -days 2 -extfile ldap.ext 2>/dev/null
cp ldap.crt data/tls/server.crt; cp ldap.key data/tls/server.key; cp root.crt int.crt data/tls/ca/
cp "$OUT"/rendered/dirsrv/seed/*.ldif seed/; cp "$REPO/fabricctl/jinja/dirsrv/seed.py" seed/
chown -R 911:911 data; chmod 750 seed; chown -R 0:911 seed; chmod 640 seed/*

start() {
  docker run -d --name dstest --add-host ldap.lan.j-j.family:127.0.0.1 --user 911:911 --security-opt no-new-privileges:true --cap-drop ALL \
    -e DS_SUFFIX_NAME="$BASE" -e DS_LOCAL_SUFFIX="$LOCAL" -e DS_DM_PASSWORD="$DM_PW" \
    -v "$W/data:/data" -v "$W/seed:/seed:ro" \
    --health-cmd "/usr/libexec/dirsrv/dscontainer -H" --health-interval 5s --health-start-period 120s \
    fabric/dirsrv:test >/dev/null
  for i in $(seq 1 60); do
    [ "$(docker inspect -f '{{.State.Health.Status}}' dstest 2>/dev/null)" = healthy ] && return 0; sleep 3
  done
  docker logs dstest | tail -30; return 1
}
seed() {  # same steps as fabricctl/lib/fabriclib/ldap/seed_directory.py
  for _ in $(seq 1 12); do
    docker exec dstest sh -c 'dsconf localhost backend suffix list 2>/dev/null | grep -qiF "$DS_SUFFIX_NAME (" || dsconf localhost backend create --suffix "$DS_SUFFIX_NAME" --be-name userroot' >/dev/null 2>&1 &&
      docker exec dstest sh -c 'dsconf localhost backend suffix list 2>/dev/null | grep -qiF "$DS_LOCAL_SUFFIX (" || dsconf localhost backend create --suffix "$DS_LOCAL_SUFFIX" --be-name sitelocal --parent-suffix "$DS_SUFFIX_NAME"' >/dev/null 2>&1 && break
    sleep 5
  done
  docker exec dstest sh -c 'python3 /seed/seed.py /seed/*.ldif'; }
pybind() { # uri dn pw  -> prints BOUND or the LDAP error name
  docker exec -e U="$1" -e D="$2" -e P="$3" dstest python3 -c "
import ldap, os
c = ldap.initialize(os.environ['U'])
c.set_option(ldap.OPT_X_TLS_CACERTFILE, '/data/tls/ca/root.crt')
c.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_DEMAND)
c.set_option(ldap.OPT_X_TLS_NEWCTX, 0)
try:
    c.simple_bind_s(os.environ['D'], os.environ['P']); print('BOUND', c.whoami_s())
except ldap.LDAPError as e:
    print(type(e).__name__, e.args[0].get('info', ''))" 2>&1; }

check "container starts healthy as uid 911 with caps dropped" start
out=$(seed); echo "$out" | sed 's/^/    /'
check "first seed adds tree + accounts" "grep -q 'seed: ' <<<\"\$out\" && ! grep -q 'seed: 0 added' <<<\"\$out\""
check "first seed asks for restart (cn=config changed)" "grep -q RESTART_REQUIRED <<<\"\$out\""
docker restart dstest >/dev/null; sleep 3
for i in $(seq 1 40); do [ "$(docker inspect -f '{{.State.Health.Status}}' dstest)" = healthy ] && break; sleep 3; done
out2=$(seed); echo "$out2" | sed 's/^/    /'
check "second seed is a no-op (idempotent)" "grep -q 'seed: 0 added, 0 modified' <<<\"\$out2\" && ! grep -q RESTART <<<\"\$out2\""

SA="cn=super_admin,ou=admins,$LOCAL"
check "role account binds over LDAPI with generated secret" "pybind 'ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket' '$SA' Sa1 | grep -q BOUND"
check "role account binds over LDAPS (3636) with CA-verified cert" "pybind 'ldaps://ldap.lan.j-j.family:3636' '$SA' Sa1 | grep -q BOUND"
check "plaintext simple bind on 3389 is refused" "pybind 'ldap://127.0.0.1:3389' '$SA' Sa1 | grep -q CONFIDENTIALITY_REQUIRED"
check "old default password no longer works" "! pybind 'ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket' '$SA' initialpassword123 | grep -q BOUND"
check "TLS < 1.2 refused" "! echo | openssl s_client -connect \$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' dstest):3636 -tls1_1 2>/dev/null | grep -q 'Cipher is [A-Z]'"
anon=$(docker exec dstest python3 -c "
import ldap
ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
c = ldap.initialize('ldaps://127.0.0.1:3636'); c.simple_bind_s('', '')
print('ORG', c.search_s('ou=groups,$BASE', ldap.SCOPE_ONELEVEL, '(cn=admins)', ['cn', 'gidNumber', 'sn']))
print('LOCAL', c.search_s('ou=admins,$LOCAL', ldap.SCOPE_ONELEVEL, '(cn=super_admin)', ['cn', 'userPassword']))" 2>&1)
check "anonymous (TLS) sees the organisation's POSIX attrs but not sn" "grep -q \"ORG.*b'admins'.*gidNumber\" <<<\"\$anon\" && ! grep -q \"'sn'\" <<<\"\$anon\""
check "anonymous (TLS) sees none of the local service accounts" "grep -q '^LOCAL \[\]' <<<\"\$anon\""
aci=$(docker exec -e P=Ga1 dstest python3 -c "
import ldap, os
c = ldap.initialize('ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket')
c.simple_bind_s('cn=group_admin,ou=admins,$LOCAL', os.environ['P'])
c.modify_s('cn=admins,ou=groups,$BASE', [(ldap.MOD_ADD, 'member', [b'$SA'])]); print('GROUP_OK')
try:
    c.modify_s('$SA', [(ldap.MOD_REPLACE, 'sn', [b'pwned'])]); print('ESCALATED')
except ldap.INSUFFICIENT_ACCESS: print('DENIED')" 2>&1)
check "group_admin can manage groups" "grep -q GROUP_OK <<<\"\$aci\""
check "group_admin cannot modify admin accounts" "grep -q DENIED <<<\"\$aci\""

# ---- first admin (fabriclib/ldap/ensure_admin_user.py, setup's admin step)
echo "--- admin user"
USERDN="uid=jim,ou=users,ou=accounts,$BASE"
first=$(REPO="$REPO" BASE="$BASE" PW='JimPass!23' python3 "$REPO/tests/dirsrv/admin_user.py" 2>&1)
check "admin user created and added to admins" "[ \"\$first\" = created+member ]"
check "admin user binds with its initial password" "pybind 'ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket' '$USERDN' 'JimPass!23' | grep -q BOUND"
check "admin user is a member of cn=admins" "docker exec -e P=Sa1 dstest python3 -c \"
import ldap, os
c = ldap.initialize('ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket'); c.simple_bind_s('$SA', os.environ['P'])
print(c.search_s('cn=admins,ou=groups,$BASE', ldap.SCOPE_BASE, attrlist=['member']))\" | grep -qi 'uid=jim'"
mo=$(docker exec -e P=Sa1 dstest python3 -c "
import ldap, os
c = ldap.initialize('ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket'); c.simple_bind_s('$SA', os.environ['P'])
print(c.search_s('$USERDN', ldap.SCOPE_BASE, attrlist=['memberOf', 'entryUUID']))" 2>&1)
check "memberOf and entryUUID plugins active" "grep -q 'cn=admins' <<<\"\$mo\" && grep -q entryUUID <<<\"\$mo\""
second=$(REPO="$REPO" BASE="$BASE" PW='Other!pw9' python3 "$REPO/tests/dirsrv/admin_user.py" 2>&1)
check "re-run leaves an existing user alone" "[ \"\$second\" = exists ]"
check "re-run did not change the password" "pybind 'ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket' '$USERDN' 'JimPass!23' | grep -q BOUND"
# the site part is a sub-suffix under the organisation: the organisation's read grants must not reach it
part=$(docker exec -e P='JimPass!23' -e G=Ga1 dstest python3 -c "
import ldap, os
for who, pw in (('$USERDN', os.environ['P']), ('cn=group_admin,ou=admins,$LOCAL', os.environ['G'])):
    c = ldap.initialize('ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket'); c.simple_bind_s(who, pw)
    org = c.search_s('ou=groups,$BASE', ldap.SCOPE_ONELEVEL, '(cn=admins)', ['cn'])
    site = c.search_s('$LOCAL', ldap.SCOPE_SUBTREE, '(objectClass=*)', ['cn'])
    print(who.split(',')[0], 'org', len(org), 'site', len(site))" 2>&1)
check "a person and another service account read the organisation, not the site part" \
    "grep -qx 'uid=jim org 1 site 0' <<<\"\$part\" && grep -qx 'cn=group_admin org 1 site 0' <<<\"\$part\""

# ---- POSIX identities (fabriclib/ldap/ensure_posix_identities.py, the DNA plugin)
echo "--- POSIX identities"
REPO="$REPO" BASE="$BASE" python3 "$REPO/tests/dirsrv/posix.py" | tee "$W/posix.log"
PASS=$((PASS + $(grep -c '^PASS' "$W/posix.log"))); FAIL=$((FAIL + $(grep -c '^FAIL' "$W/posix.log")))

# ---- device RBAC (fabriclib/ldap device + role operations as cn=device_admin)
echo "--- devices and roles"
REPO="$REPO" BASE="$BASE" python3 "$REPO/tests/dirsrv/devices.py" | tee "$W/devices.log"
PASS=$((PASS + $(grep -c '^PASS' "$W/devices.log"))); FAIL=$((FAIL + $(grep -c '^FAIL' "$W/devices.log")))

# ---- upgrade from before the directory split (fabriclib/ldap/migrate_local_suffix.py)
echo "--- migration to the local suffix"
REPO="$REPO" BASE="$BASE" python3 "$REPO/tests/dirsrv/migrate.py" | tee "$W/migrate.log"
PASS=$((PASS + $(grep -c '^PASS' "$W/migrate.log"))); FAIL=$((FAIL + $(grep -c '^FAIL' "$W/migrate.log")))

echo; echo "$PASS passed, $FAIL failed"
docker rm -f dstest >/dev/null 2>&1
exit $FAIL
