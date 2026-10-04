#!/bin/bash
# S0 spike Q11: migration. A real 389-DS from fabric's image and rendered seed, filled the way fabric fills it, is
# exported and written into AD; every person, group, id, device, role and network must arrive. Needs the DC of
# q1-q2.sh with fabric's schema (q3-q6.sh).   sudo bash spikes/samba/q11.sh
. "$(dirname "$0")/common.sh"
REPO="$(cd "$HERE/../.." && pwd)"
Q=$W/q11; OLD="dc=lan,dc=j-j,dc=family"; LOCAL="ou=pi-core,$OLD"
dx() { docker exec s0-dc "$@"; }
echo "--- Q11"
docker rm -f s0-ds >/dev/null 2>&1; rm -rf "$Q"; mkdir -p "$Q/data/tls/ca" "$Q/seed"
python3 "$REPO/tests/render.py" "$Q/rendered" >/dev/null || { echo "FAIL render"; exit 1; }
docker build -q --build-arg BASE_IMAGE="$(python3 "$REPO/tests/image_ref.py" debian)" --build-arg DS_UID=911 \
    --build-arg DS_GID=911 -t fabric/dirsrv:test "$REPO/packaging/images/dirsrv" >/dev/null || { echo "FAIL image"; exit 1; }
# a root CA and a server certificate it signs (389-DS needs its own Server-Cert apart from the CA: its backends'
# attribute encryption uses that key)
(cd "$Q" && openssl req -x509 -newkey rsa:2048 -nodes -keyout root.key -out root.crt -days 2 -subj /CN=Spike-Root \
    -addext basicConstraints=critical,CA:TRUE -addext keyUsage=critical,keyCertSign,cRLSign 2>/dev/null \
    && openssl req -newkey rsa:2048 -nodes -keyout data/tls/server.key -out ldap.csr -subj /CN=ldap.lan.j-j.family 2>/dev/null \
    && printf 'subjectAltName=DNS:ldap.lan.j-j.family\nextendedKeyUsage=serverAuth,clientAuth\n' > ldap.ext \
    && openssl x509 -req -in ldap.csr -CA root.crt -CAkey root.key -CAcreateserial -out data/tls/server.crt -days 2 \
        -extfile ldap.ext 2>/dev/null && cp root.crt data/tls/ca/)
cp "$Q"/rendered/dirsrv/seed/*.ldif "$Q/seed/"; cp "$REPO/src/containers/dirsrv/seed.py" "$Q/seed/"
chown -R 911:911 "$Q/data"; chmod 750 "$Q/seed"; chown -R 0:911 "$Q/seed"; chmod 640 "$Q"/seed/*
docker run -d --name s0-ds --add-host ldap.lan.j-j.family:127.0.0.1 --user 911:911 --cap-drop ALL \
    --security-opt no-new-privileges:true -e DS_SUFFIX_NAME="$OLD" -e DS_LOCAL_SUFFIX="$LOCAL" -e DS_DM_PASSWORD=DmPass1 \
    -v "$Q/data:/data" -v "$Q/seed:/seed:ro" --health-cmd "/usr/libexec/dirsrv/dscontainer -H" --health-interval 5s \
    --health-start-period 120s fabric/dirsrv:test >/dev/null
healthy() { for _ in $(seq 1 60); do [ "$(docker inspect -f '{{.State.Health.Status}}' s0-ds)" = healthy ] && return 0; sleep 3; done; return 1; }
seed() {  # the steps of fabriclib/ldap/seed_directory.py, as the dirsrv suite runs them
    for _ in $(seq 1 12); do
        docker exec s0-ds sh -c 'dsconf localhost backend suffix list 2>/dev/null | grep -qiF "$DS_SUFFIX_NAME (" || dsconf localhost backend create --suffix "$DS_SUFFIX_NAME" --be-name userroot' >/dev/null 2>&1 &&
        docker exec s0-ds sh -c 'dsconf localhost backend suffix list 2>/dev/null | grep -qiF "$DS_LOCAL_SUFFIX (" || dsconf localhost backend create --suffix "$DS_LOCAL_SUFFIX" --be-name sitelocal --parent-suffix "$DS_SUFFIX_NAME"' >/dev/null 2>&1 && break
        sleep 5
    done
    docker exec s0-ds sh -c 'python3 /seed/seed.py /seed/*.ldif' >/dev/null
}
healthy && seed && docker restart s0-ds >/dev/null && healthy && seed && echo "PASS fabric's 389-DS seeded (its own image and seed)" \
    || { echo "FAIL 389-DS"; docker logs s0-ds 2>&1 | tail -5; exit 1; }
REPO="$REPO" BASE="$OLD" W="$Q" python3 "$HERE/q11-populate.py" | tail -1
python3 "$HERE/q11-migrate.py" "$Q/export.json" "$OLD" "$B" pi-core "$Q/ad"
# into AD on the DC, as fabric's deploy would (root, the DC's own database)
for ou in "OU=sites,$B" "OU=pi-core,OU=sites,$B"; do
    printf 'dn: %s\nobjectClass: organizationalUnit\n' "$ou" | docker exec -i s0-dc sh -c 'cat > /tmp/ou.ldif'
    dx ldbadd -H /data/private/sam.ldb /tmp/ou.ldif >/dev/null 2>&1
done
# the containers one by one (a re-run finds them there), then the entries
awk -v RS= -v dir="$Q/ad" '{print > (dir "/ou" NR ".ldif")}' "$Q/ad/ous.ldif"
for f in "$Q"/ad/ou[0-9]*.ldif; do
    docker exec -i s0-dc sh -c "cat > /tmp/ou.ldif" < "$f"; dx ldbadd -H /data/private/sam.ldb /tmp/ou.ldif >/dev/null 2>&1
done
for f in add modify; do
    docker exec -i s0-dc sh -c "cat > /tmp/$f.ldif" < "$Q/ad/$f.ldif"
    [ "$f" = modify ] && tool=ldbmodify || tool=ldbadd
    r=$(dx $tool -H /data/private/sam.ldb "/tmp/$f.ldif" 2>&1 | grep -v smb.conf | tail -2)
    echo "$r" | grep -qE "successfully|^$" || echo "FAIL loading $f.ldif: $r"
done
# compare: what 389-DS had against what AD now has
python3 - "$Q/export.json" "$Q/ad/plan.json" > "$Q/expect.txt" <<'PY'
import json, sys
entries, plan = json.load(open(sys.argv[1])), json.load(open(sys.argv[2]))
def one(a, k): return (a.get(k) or [""])[0]
for dn, a in entries:
    oc = {o.lower() for o in a.get("objectClass", [])}
    if "posixaccount" in oc and ",ou=users,ou=accounts," in dn.lower():
        print(f"person {one(a, 'uid')} {one(a, 'uidNumber')} {one(a, 'gidNumber')}")
    elif "fabricdevice" in oc:
        print(f"device {one(a, 'cn')} {','.join(sorted(m.lower() for m in a.get('macAddress', [])))} "
              f"{','.join(sorted(a.get('fabricRoleName', [])))} {len(a.get('fabricCertFingerprint', []))}")
    elif "fabricrole" in oc:
        print(f"role {one(a, 'cn')} {one(a, 'fabricVlan')} {','.join(sorted(a.get('fabricPermission', [])))}")
    elif "fabricnetwork" in oc:
        print(f"network {one(a, 'cn')} {one(a, 'fabricCidr')}")
    elif "posixgroup" in oc and ",ou=groups," in dn.lower():
        # fabric's "users" (everyone) is AD's Domain Users
        name = "Domain Users" if one(a, "cn").lower() == "users" else one(a, "cn")
        print(f"group {name} {one(a, 'gidNumber')}")
PY
docker exec -i s0-dc python3 - "$B" > "$Q/got.txt" 2>"$Q/got.err" <<'PY'
import sys
from samba.auth import system_session
from samba.param import LoadParm
from samba.samdb import SamDB
lp = LoadParm(); lp.load("/data/etc/smb.conf")
db = SamDB(url=lp.private_path("sam.ldb"), session_info=system_session(), lp=lp)
def s(f, attrs): return db.search(base=sys.argv[1], expression=f, attrs=attrs)
def one(r, k): return str(r[k][0]) if k in r else ""
def many(r, k): return [str(v) for v in r[k]] if k in r else []
for r in s("(&(objectClass=user)(uidNumber=*)(!(objectClass=computer)))", ["sAMAccountName", "uidNumber", "gidNumber"]):
    print(f"person {one(r, 'sAMAccountName')} {one(r, 'uidNumber')} {one(r, 'gidNumber')}")
for r in s("(objectClass=fabricDevice)", ["cn", "macAddress", "fabricRoleName", "fabricCertFingerprint"]):
    print(f"device {one(r, 'cn')} {','.join(sorted(m.lower() for m in many(r, 'macAddress')))} "
          f"{','.join(sorted(many(r, 'fabricRoleName')))} {len(many(r, 'fabricCertFingerprint'))}")
for r in s("(objectClass=fabricRole)", ["cn", "fabricVlan", "fabricPermission"]):
    print(f"role {one(r, 'cn')} {one(r, 'fabricVlan')} {','.join(sorted(many(r, 'fabricPermission')))}")
for r in s("(objectClass=fabricNetwork)", ["cn", "fabricCidr"]):
    print(f"network {one(r, 'cn')} {one(r, 'fabricCidr')}")
for r in s("(&(objectClass=group)(gidNumber=*))", ["sAMAccountName", "gidNumber"]):
    print(f"group {one(r, 'sAMAccountName')} {one(r, 'gidNumber')}")
PY
missing=$(sort "$Q/expect.txt" | comm -23 - <(sort "$Q/got.txt"))
[ -s "$Q/expect.txt" ] && [ -z "$missing" ] \
    && echo "PASS every person (with ids), device (MACs, roles, fingerprints), role (VLAN, permissions) and network arrived ($(wc -l < "$Q/expect.txt") entries)" \
    || { echo "FAIL missing or different in AD:"; echo "$missing" | sed 's/^/    /'; }
gid=$(dx ldbsearch -H /data/private/sam.ldb -b "$B" "(sAMAccountName=Domain Users)" gidNumber 2>/dev/null | sed -n 's/^gidNumber: //p')
[ "$gid" = 5000 ] && echo "PASS fabric's everyone-group became Domain Users with fabric's gid (5000)" || echo "FAIL Domain Users gid: $gid"
dx ldbsearch -H /data/private/sam.ldb -b "$B" "(sAMAccountName=admins)" member 2>/dev/null | grep -qi "CN=carol,OU=people" \
    && echo "PASS group membership arrived (carol in admins)" || echo "FAIL admins membership"
uac=$(dx ldbsearch -H /data/private/sam.ldb -b "$B" "(sAMAccountName=carol)" userAccountControl 2>/dev/null | sed -n 's/^userAccountControl: //p')
[ $(( ${uac:-0} & 2 )) -eq 2 ] && echo "PASS migrated people are disabled until they set a password (no password moves)" \
    || echo "FAIL carol's account control: $uac"
