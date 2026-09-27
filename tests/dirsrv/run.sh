#!/bin/bash
# 389-DS integration test: real image, compose-equivalent hardening, our seed
# data (rendered by tests/render.py into $FABRIC_TEST_OUT/rendered), TLS and migration.
set -uo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
OUT="${FABRIC_TEST_OUT:-/tmp/fabric-tests}"
W=$OUT/dirsrv
BASE="dc=lan,dc=j-j,dc=family"
DM_PW='DmPass1'
PASS=0; FAIL=0
check() { if eval "$2"; then echo "PASS $1"; PASS=$((PASS+1)); else echo "FAIL $1"; FAIL=$((FAIL+1)); fi; }

docker rm -f dstest oldldap >/dev/null 2>&1
docker build -q --build-arg DS_UID=911 --build-arg DS_GID=911 -t core-template/dirsrv:local "$REPO/fabric/jinja/dirsrv/build" >/dev/null || { echo "FAIL image build"; exit 1; }
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
cp "$OUT"/rendered/dirsrv/seed/*.ldif seed/; cp "$REPO/fabric/jinja/dirsrv/seed.py" seed/
chown -R 911:911 data; chmod 750 seed; chown -R 0:911 seed; chmod 640 seed/*

start() {
  docker run -d --name dstest --add-host ldap.lan.j-j.family:127.0.0.1 --user 911:911 --security-opt no-new-privileges:true --cap-drop ALL \
    -e DS_SUFFIX_NAME="$BASE" -e DS_DM_PASSWORD="$DM_PW" \
    -v "$W/data:/data" -v "$W/seed:/seed:ro" \
    --health-cmd "/usr/libexec/dirsrv/dscontainer -H" --health-interval 5s --health-start-period 120s \
    core-template/dirsrv:local >/dev/null
  for i in $(seq 1 60); do
    [ "$(docker inspect -f '{{.State.Health.Status}}' dstest 2>/dev/null)" = healthy ] && return 0; sleep 3
  done
  docker logs dstest | tail -30; return 1
}
seed() {  # same steps as dirsrv_seed in fabric/lib/dirsrv.sh
  docker exec dstest sh -c 'dsconf localhost backend suffix list 2>/dev/null | grep -qiF "$DS_SUFFIX_NAME (" || dsconf localhost backend create --suffix "$DS_SUFFIX_NAME" --be-name userroot' >/dev/null
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

SA="cn=super_admin,ou=admins,ou=accounts,$BASE"
check "role account binds over LDAPI with generated secret" "pybind 'ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket' '$SA' Sa1 | grep -q BOUND"
check "role account binds over LDAPS (3636) with CA-verified cert" "pybind 'ldaps://ldap.lan.j-j.family:3636' '$SA' Sa1 | grep -q BOUND"
check "plaintext simple bind on 3389 is refused" "pybind 'ldap://127.0.0.1:3389' '$SA' Sa1 | grep -q CONFIDENTIALITY_REQUIRED"
check "old default password no longer works" "! pybind 'ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket' '$SA' initialpassword123 | grep -q BOUND"
check "TLS < 1.2 refused" "! echo | openssl s_client -connect \$(docker inspect -f '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}' dstest):3636 -tls1_1 2>/dev/null | grep -q 'Cipher is [A-Z]'"
anon=$(docker exec dstest python3 -c "
import ldap
ldap.set_option(ldap.OPT_X_TLS_REQUIRE_CERT, ldap.OPT_X_TLS_NEVER)
c = ldap.initialize('ldaps://127.0.0.1:3636'); c.simple_bind_s('', '')
r = c.search_s('ou=admins,ou=accounts,$BASE', ldap.SCOPE_ONELEVEL, '(cn=super_admin)', ['cn', 'userPassword', 'sn'])
print(r)" 2>&1)
check "anonymous (TLS) sees POSIX attrs but not passwords or sn" "grep -q \"b'super_admin'\" <<<\"\$anon\" && ! grep -qi 'userPassword\|sn' <<<\"\$anon\""
aci=$(docker exec -e P=Ga1 dstest python3 -c "
import ldap, os
c = ldap.initialize('ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket')
c.simple_bind_s('cn=group_admin,ou=admins,ou=accounts,$BASE', os.environ['P'])
c.modify_s('cn=admins,ou=groups,$BASE', [(ldap.MOD_ADD, 'member', [b'$SA'])]); print('GROUP_OK')
try:
    c.modify_s('$SA', [(ldap.MOD_REPLACE, 'sn', [b'pwned'])]); print('ESCALATED')
except ldap.INSUFFICIENT_ACCESS: print('DENIED')" 2>&1)
check "group_admin can manage groups" "grep -q GROUP_OK <<<\"\$aci\""
check "group_admin cannot modify admin accounts" "grep -q DENIED <<<\"\$aci\""
mo=$(docker exec -e P=Sa1 dstest python3 -c "
import ldap, os
c = ldap.initialize('ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket'); c.simple_bind_s('$SA', os.environ['P'])
print(c.search_s('$SA', ldap.SCOPE_BASE, attrlist=['memberOf', 'entryUUID']))" 2>&1)
check "memberOf and entryUUID plugins active" "grep -q 'cn=admins' <<<\"\$mo\" && grep -q entryUUID <<<\"\$mo\""

# ---- migration from a real osixia OpenLDAP
echo "--- migration"
mkdir -p old/data old/config
docker run -d --name oldldap -e LDAP_DOMAIN=lan.j-j.family -e LDAP_ADMIN_PASSWORD=admin \
  -v "$W/old/data:/var/lib/ldap" -v "$W/old/config:/etc/ldap/slapd.d" osixia/openldap:1.5.0 >/dev/null
sleep 25
cat > old.ldif <<EOF
dn: ou=accounts,$BASE
objectClass: organizationalUnit
ou: accounts

dn: ou=users,ou=accounts,$BASE
objectClass: organizationalUnit
ou: users

dn: ou=groups,$BASE
objectClass: organizationalUnit
ou: groups

dn: uid=jim,ou=users,ou=accounts,$BASE
objectClass: inetOrgPerson
objectClass: posixAccount
uid: jim
cn: Jim
sn: Church
uidNumber: 5001
gidNumber: 5000
homeDirectory: /home/jim
userPassword: {SSHA}$(python3 -c "import hashlib,os,base64;s=os.urandom(4);print(base64.b64encode(hashlib.sha1(b'JimPass!23'+s).digest()+s).decode())")

dn: cn=admins,ou=groups,$BASE
objectClass: groupOfNames
cn: admins
member: cn=admin,$BASE
member: uid=jim,ou=users,ou=accounts,$BASE
EOF
docker cp old.ldif oldldap:/tmp/old.ldif
docker exec oldldap ldapadd -x -H ldap://localhost -D "cn=admin,$BASE" -w admin -f /tmp/old.ldif >/dev/null
OLD_UUID=$(docker exec oldldap ldapsearch -x -H ldap://localhost -D "cn=admin,$BASE" -w admin -b "uid=jim,ou=users,ou=accounts,$BASE" -s base entryUUID | awk '/^entryUUID/{print $2}')
docker stop oldldap >/dev/null
# run the real migration script, minus the Keycloak step
sed -e 's/^DS=dirsrv$/DS=dstest/' \
    -e "s#^LIB_DIR=.*#LIB_DIR=$REPO/fabric/lib#" -e 's/^dirsrv_wait_healthy$/true/' -e 's/systemctl is-active --quiet keycloak/false/' \
    "$REPO/fabric/lib/ldap_migrate.sh" > migrate.sh
mig=$(bash migrate.sh "$W/old" osixia/openldap:1.5.0 2>&1); echo "$mig" | sed 's/^/    /'
check "migration imports user and merges group" "grep -q 'migrate: 1 added, 1 groups merged' <<<\"\$mig\""
check "migrated user keeps entryUUID ($OLD_UUID)" "docker exec -e P=Sa1 dstest python3 -c \"
import ldap, os
c = ldap.initialize('ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket'); c.simple_bind_s('$SA', os.environ['P'])
print(c.search_s('uid=jim,ou=users,ou=accounts,$BASE', ldap.SCOPE_BASE, attrlist=['entryUUID']))\" | grep -q '$OLD_UUID'"
check "migrated user logs in with old SSHA password" "pybind 'ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket' 'uid=jim,ou=users,ou=accounts,$BASE' 'JimPass!23' | grep -q BOUND"
check "osixia cn=admin dropped from group" "! docker exec -e P=Sa1 dstest python3 -c \"
import ldap, os
c = ldap.initialize('ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket'); c.simple_bind_s('$SA', os.environ['P'])
print(c.search_s('cn=admins,ou=groups,$BASE', ldap.SCOPE_BASE, attrlist=['member']))\" | grep -q 'cn=admin,dc'"
mig2=$(bash migrate.sh "$W/old" osixia/openldap:1.5.0 2>&1)
check "migration is re-runnable" "grep -q 'migrate: 0 added, 0 groups merged' <<<\"\$mig2\""

echo; echo "$PASS passed, $FAIL failed"
docker rm -f dstest oldldap >/dev/null 2>&1
exit $FAIL
