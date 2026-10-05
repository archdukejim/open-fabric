#!/bin/bash
# -----------------------------------------------------------------------
# Directory replication between two sites (manual 1.8.3.2, M5) with two real 389-DS containers:
# the root (ldap.lan.test) writes the organisation, the site (ldap.lab.lan.test) writes its own part. Proves:
# the organisation reaches the site read-only, the site's part reaches the root, writes at the wrong end are
# refused, the site keeps answering with the root down and catches up afterwards. fabriclib's
# configure_replica / configure_agreement do the work; secrets travel in the environment only.
# -----------------------------------------------------------------------
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="${REPO:-$(cd "$HERE/../.." && pwd)}"
LIB="$REPO/src"
OUT="${FABRIC_TEST_OUT:-/tmp/fabric-tests}"
W="$OUT/replication"
BASE="dc=lan,dc=test"; ROOT_PART="ou=lan,$BASE"; SITE_PART="ou=lab,$BASE"
NET=repl_test_net
PASS=0; FAIL=0
check() { if eval "$2"; then echo "PASS $1"; PASS=$((PASS+1)); else echo "FAIL $1"; FAIL=$((FAIL+1)); fi; }
cleanup() { docker rm -f dsroot dssite >/dev/null 2>&1; docker network rm "$NET" >/dev/null 2>&1; }
cleanup; rm -rf "$W"; mkdir -p "$W"; cd "$W" || exit 1
docker build -q --build-arg BASE_IMAGE="$(python3 "$REPO/tests/image_ref.py" debian)" --build-arg DS_UID=911 \
  --build-arg DS_GID=911 -t fabric/dirsrv:test "$REPO/packaging/images/dirsrv" >/dev/null || { echo "FAIL image"; exit 1; }
docker network create "$NET" >/dev/null

# one CA for the organisation, a server certificate per site
openssl req -x509 -newkey rsa:2048 -nodes -keyout ca.key -out ca.crt -days 2 -subj '/CN=Test Org CA' \
  -addext basicConstraints=critical,CA:TRUE -addext keyUsage=critical,keyCertSign,cRLSign 2>/dev/null
for h in ldap.lan.test ldap.lab.lan.test; do
  openssl req -newkey rsa:2048 -nodes -keyout "$h.key" -out "$h.csr" -subj "/CN=$h" 2>/dev/null
  printf "subjectAltName=DNS:%s\nextendedKeyUsage=serverAuth,clientAuth\n" "$h" > "$h.ext"
  openssl x509 -req -in "$h.csr" -CA ca.crt -CAkey ca.key -CAcreateserial -out "$h.crt" -days 2 -extfile "$h.ext" 2>/dev/null
  mkdir -p "$h/tls/ca"; cp "$h.crt" "$h/tls/server.crt"; cp "$h.key" "$h/tls/server.key"; cp ca.crt "$h/tls/ca/"
  chown -R 911:911 "$h"
done

start() {  # name host local-suffix
  docker run -d --name "$1" --network "$NET" --network-alias "$2" --user 911:911 --cap-drop ALL \
    --security-opt no-new-privileges:true -e DS_SUFFIX_NAME="$BASE" -e DS_DM_PASSWORD=DmPass-1 \
    -v "$W/$2:/data" --health-cmd "/usr/libexec/dirsrv/dscontainer -H" --health-interval 5s \
    --health-start-period 120s fabric/dirsrv:test >/dev/null
  for i in $(seq 1 60); do [ "$(docker inspect -f '{{.State.Health.Status}}' "$1")" = healthy ] && return 0; sleep 3; done
  docker logs "$1" | tail -20; return 1
}
dm() {  # container python-code -> output (python-ldap as Directory Manager over LDAPI)
  docker exec -i "$1" python3 - <<PY
import ldap, ldap.modlist, os, time
c = ldap.initialize("ldapi://%2Fdata%2Frun%2Fslapd-localhost.socket")
c.simple_bind_s("cn=Directory Manager", os.environ["DS_DM_PASSWORD"])
$2
PY
}
backend() {  # container suffix be-name [parent]
  docker exec "$1" dsconf localhost backend create --suffix "$2" --be-name "$3" ${4:+--parent-suffix "$4"} >/dev/null 2>&1; }
py() { PYTHONPATH="$LIB" python3 -c "$1"; }

start dsroot ldap.lan.test; start dssite ldap.lab.lan.test
# the root: the organisation (written here) and its own part
backend dsroot "$BASE" userroot; backend dsroot "$ROOT_PART" sitelocal "$BASE"
dm dsroot "
for dn, a in ((\"$BASE\", {'objectClass': [b'top', b'domain'], 'dc': [b'lan']}),
              (\"ou=users,$BASE\", {'objectClass': [b'top', b'organizationalUnit'], 'ou': [b'users']}),
              (\"uid=alice,ou=users,$BASE\", {'objectClass': [b'top', b'inetOrgPerson'], 'uid': [b'alice'], 'cn': [b'alice'], 'sn': [b'a']}),
              (\"$ROOT_PART\", {'objectClass': [b'top', b'organizationalUnit'], 'ou': [b'lan']})):
    c.add_s(dn, ldap.modlist.addModlist(a))"
# the site: an empty copy of the organisation (filled by the root) and its own part with a device
backend dssite "$BASE" userroot; backend dssite "$SITE_PART" sitelocal "$BASE"
dm dssite "
for dn, a in ((\"$SITE_PART\", {'objectClass': [b'top', b'organizationalUnit'], 'ou': [b'lab']}),
              (\"cn=printer,$SITE_PART\", {'objectClass': [b'top', b'device'], 'cn': [b'printer']})):
    c.add_s(dn, ldap.modlist.addModlist(a))"

SECRET=$(openssl rand -base64 24)
export SECRET W
# while the links are set up, watch every process's command line for the secret (it must travel only in
# environments); the watcher holds it in its environment too, never in its own arguments
python3 - > "$W/leak.txt" <<'PY' &
import glob, os, time
s, found = os.environ["SECRET"].encode(), False
end = time.time() + 120
while time.time() < end and not os.path.exists(os.environ["W"] + "/link.done"):
    for p in glob.glob("/proc/[0-9]*/cmdline"):
        try:
            found = found or s in open(p, "rb").read()
        except OSError:
            pass
    time.sleep(0.02)
print("LEAK" if found else "CLEAN")
PY
WATCH=$!
# each site's registry, as a join leaves it: the root lists lab, lab names its upstream
cat > "$W/root.yaml" <<YAML
sites: {lab: {ldap_host: ldap.lab.lan.test, ldap_port: 3636}}
YAML
cat > "$W/site.yaml" <<YAML
upstream: {site_name: lan, ldap_host: ldap.lan.test, ldap_port: 3636}
YAML
link=$(py "
import os
from fabriclib.federation.configure_directory_links import configure_directory_links as links
s, w = os.environ['SECRET'], os.environ['W']
root = {'site_name': 'lan', 'ldap_base_dn': '$BASE', 'ldap_local_dn': '$ROOT_PART'}
site = {'site_name': 'lab', 'ldap_base_dn': '$BASE', 'ldap_local_dn': '$SITE_PART'}
print(links(site, {'federation_replication': {'upstream': s}}, w + '/site.yaml', container='dssite'))
print(links(root, {'federation_replication': {'lab': s}}, w + '/root.yaml', container='dsroot'))
print(links(root, {'federation_replication': {'lab': s}}, w + '/root.yaml', container='dsroot'))
" 2>&1)
touch "$W/link.done"; wait "$WATCH"
echo "$link" | sed 's/^/    /'
check "replicas, the copy of lab's part and the agreements set up; a second run changes nothing" "tail -1 <<<\"\$link\" | grep -qx '\[\]'"
check "the link secret never appears on any command line while links are set up" "grep -qx CLEAN '$W/leak.txt'"

seen() {  # container dn -> 0 when found within 60 s
  for i in $(seq 1 30); do
    dm "$1" "print(len(c.search_s(\"$2\", ldap.SCOPE_BASE, '(objectClass=*)')))" 2>/dev/null | grep -qx 1 && return 0; sleep 2
  done; return 1; }
check "the organisation reaches the site (a person written at the root)" "seen dssite 'uid=alice,ou=users,$BASE'"
check "the site's part reaches the root (a device written at the site)" "seen dsroot 'cn=printer,$SITE_PART'"
refused=$(dm dssite "
try:
    c.add_s(\"uid=mallory,ou=users,$BASE\", ldap.modlist.addModlist({'objectClass': [b'top', b'inetOrgPerson'], 'uid': [b'mallory'], 'cn': [b'm'], 'sn': [b'm']}))
    print('WRITTEN')
except ldap.REFERRAL:
    print('REFERRAL')
except ldap.LDAPError as e:
    print(type(e).__name__)" 2>&1)
echo "    a write at the site: $refused"
check "a write to the organisation at the site is refused and referred to the root" "grep -qx REFERRAL <<<\"\$refused\""

docker stop dsroot >/dev/null
check "with the root down the site still answers from its copy" "seen dssite 'uid=alice,ou=users,$BASE'"
dm dssite "c.add_s(\"cn=camera,$SITE_PART\", ldap.modlist.addModlist({'objectClass': [b'top', b'device'], 'cn': [b'camera']}))"
docker start dsroot >/dev/null
for i in $(seq 1 60); do [ "$(docker inspect -f '{{.State.Health.Status}}' dsroot)" = healthy ] && break; sleep 3; done
dm dsroot "c.add_s(\"uid=bob,ou=users,$BASE\", ldap.modlist.addModlist({'objectClass': [b'top', b'inetOrgPerson'], 'uid': [b'bob'], 'cn': [b'bob'], 'sn': [b'b']}))"
check "changes made while the root was down arrive when it is back" "seen dsroot 'cn=camera,$SITE_PART'"
check "and the root's new changes reach the site" "seen dssite 'uid=bob,ou=users,$BASE'"

# ---- a site removed from the federation
echo "sites: {}" > "$W/root.yaml"
gone=$(py "
from fabriclib.federation.configure_directory_links import configure_directory_links as links
print(links({'site_name': 'lan', 'ldap_base_dn': '$BASE', 'ldap_local_dn': '$ROOT_PART'}, {'federation_replication': {}},
            '$W/root.yaml', container='dsroot'))" 2>&1)
check "a removed site's agreement goes (its copy stays: data is never deleted automatically)"     "grep -q 'agreement to-lab' <<<\"\$gone\" && seen dsroot 'cn=printer,$SITE_PART'"

echo; echo "$PASS passed, $FAIL failed"
[ "$FAIL" -gt 0 ] && { docker logs dssite 2>&1 | grep -i repl | tail -15; docker logs dsroot 2>&1 | grep -i repl | tail -15; }
cleanup
exit "$FAIL"
