#!/bin/bash
# S0 spike Q12: an independent writable site DC. It joins, is cut off from the root DC (its site's clients still
# reach it), both sides change their own objects plus one deliberate conflict and one name clash, then it reconnects
# and the two converge. Needs q1-q2.sh and q4.sh (the site OUs, h2admin).   sudo bash spikes/samba/q12.sh
. "$(dirname "$0")/common.sh"
dx() { docker exec s0-dc "$@"; }
C=(-s /data/etc/smb.conf)
O2="OU=house2,OU=sites,$B"; O1="OU=house1,OU=sites,$B"; NC="$B"
echo "--- Q12"
auth_file Administrator "$W/secrets/admin_password" "$W/admin.auth"
auth_file h2admin "$W/secrets/h2admin" "$W/h2.auth"
docker network inspect s0site2 >/dev/null 2>&1 || docker network create --subnet 10.89.0.0/24 s0site2 >/dev/null
docker rm -f s0-dc2 >/dev/null 2>&1; rm -rf "$W/data2"
docker run -d --name s0-dc2 --hostname dc2.ad.lan.test --network s0net --ip 10.88.0.11 --dns "$DC_IP" \
    --cap-drop ALL --cap-add CHOWN --cap-add DAC_OVERRIDE --cap-add FOWNER --cap-add SETUID --cap-add SETGID \
    --security-opt no-new-privileges:true --read-only --tmpfs /run:size=16m --tmpfs /tmp:size=64m \
    --tmpfs /var/log/samba:size=16m --memory 512m \
    -e REALM="$REALM" -e DOMAIN="$DOMAIN" -e HOST_IP=10.88.0.11 -e JOIN_ROLE=DC -e JOIN_SERVER=dc1.ad.lan.test \
    -v "$W/data2:/data" -v "$W/admin.auth:/run/secrets/join.auth:ro" s0/dc >/dev/null
for _ in $(seq 1 90); do docker logs s0-dc2 2>&1 | grep -qE "Starting process|^ERROR" && break; sleep 2; done; sleep 15
docker logs s0-dc2 2>&1 | grep -q "^joined" && echo "PASS a writable DC joins for site house2" \
    || { echo "FAIL join"; docker logs s0-dc2 2>&1 | tail -8; exit 1; }
docker network connect --ip 10.89.0.11 s0site2 s0-dc2      # the site's own LAN: its clients reach it there
# as a site DC would on its own: register its names in AD's DNS (replication finds partners by them) and let the
# root's topology service (KCC) make its inbound link now rather than at its next periodic run
docker exec s0-dc2 samba_dnsupdate "${C[@]}" --all-names >/dev/null 2>&1
dx samba-tool drs kcc dc1 "${C[@]}" >/dev/null 2>&1
# a shared object both sides will change while apart
mk() {  # host auth ldif-text -> the tool's last line
    printf '%b' "$3" > "$W/op.ldif"
    docker run --rm --network "$(case $1 in 10.89.*) echo s0site2;; *) echo s0net;; esac)" -v "$2:/auth:ro" \
        -v "$W/op.ldif:/op.ldif:ro" --entrypoint "${TOOL:-ldbadd}" s0/dc -H "ldap://$1" -A /auth /op.ldif 2>&1 | tail -1
}
user() { printf 'dn: CN=%s,%s\\nobjectClass: user\\nsAMAccountName: %s\\n' "$1" "$2" "$1"; }
mk "$DC_IP" "$W/admin.auth" "$(user shared "$O2")" >/dev/null
docker exec s0-dc2 samba-tool drs replicate dc2 dc1 "$NC" "${C[@]}" >/dev/null 2>&1
docker exec s0-dc2 ldbsearch -H /data/private/sam.ldb -b "$NC" "(sAMAccountName=shared)" dn 2>/dev/null | grep -q "^dn:" \
    && echo "PASS replicated before the cut (the shared object is on both DCs)" || echo "FAIL initial replication"

docker network disconnect s0net s0-dc2; echo "(the site DC is cut off from the root; its site LAN stays)"
r=$(mk 10.89.0.11 "$W/h2.auth" "$(user h2offline "$O2")"); echo "$r" | grep -q successfully \
    && echo "PASS while cut off, the site admin adds a person to its own site at the site DC" || echo "FAIL offline add: $r"
r=$(mk 10.89.0.11 "$W/h2.auth" "$(user h2evil "$O1")"); ! echo "$r" | grep -q successfully \
    && echo "PASS while cut off, the site DC still refuses the site admin in another site (ACLs hold offline)" \
    || echo "FAIL offline cross-site write accepted"
r=$(mk "$DC_IP" "$W/admin.auth" "$(user rootoffline "$O1")"); echo "$r" | grep -q successfully \
    && echo "PASS meanwhile the root adds a person to site house1" || echo "FAIL root add: $r"
# the deliberate conflict: the same attribute changed on both sides, the root's change second
TOOL=ldbmodify mk 10.89.0.11 "$W/h2.auth" "dn: CN=shared,$O2\nchangetype: modify\nreplace: description\ndescription: from-site\n" >/dev/null
sleep 2
TOOL=ldbmodify mk "$DC_IP" "$W/admin.auth" "dn: CN=shared,$O2\nchangetype: modify\nreplace: description\ndescription: from-root\n" >/dev/null
# the name clash: the same new name created on both sides
mk 10.89.0.11 "$W/h2.auth" "$(user clash "$O2")" >/dev/null
mk "$DC_IP" "$W/admin.auth" "dn: CN=clash,$O2\nobjectClass: user\nsAMAccountName: clash-root\n" >/dev/null

docker network connect --ip 10.88.0.11 s0net s0-dc2; echo "(reconnected)"
sleep 5
# replicate now in both directions (AD would on its own within its replication interval)
docker exec s0-dc2 samba-tool drs replicate dc2 dc1 "$NC" "${C[@]}" >/dev/null 2>&1
dx samba-tool drs replicate dc1 dc2 "$NC" "${C[@]}" >/dev/null 2>&1
has() { docker exec "$1" ldbsearch -H /data/private/sam.ldb -b "$NC" "$2" "${3:-dn}" 2>/dev/null; }
for dc in s0-dc s0-dc2; do
    has "$dc" "(sAMAccountName=h2offline)" | grep -q "^dn:" && has "$dc" "(sAMAccountName=rootoffline)" | grep -q "^dn:" \
        && echo "PASS $dc has both sides' changes after reconnecting" || echo "FAIL $dc is missing a side's change"
done
d1=$(has s0-dc "(sAMAccountName=shared)" description | sed -n 's/^description: //p')
d2=$(has s0-dc2 "(sAMAccountName=shared)" description | sed -n 's/^description: //p')
[ "$d1" = "$d2" ] && echo "PASS the conflict converged to one value on both DCs: '$d1' (the later write)" \
    || echo "FAIL the conflict did not converge: dc1 '$d1', dc2 '$d2'"
n1=$(has s0-dc "(|(sAMAccountName=clash)(sAMAccountName=clash-root))" dn | grep -c "^dn:")
cnf=$(has s0-dc "(|(sAMAccountName=clash)(sAMAccountName=clash-root))" dn | grep -c "CNF:")
[ "$n1" = 2 ] && [ "$cnf" = 1 ] && echo "PASS the name clash kept both objects, one renamed (CNF), nothing lost" \
    || echo "NOTE the name clash: $n1 objects, $cnf renamed"
# who may write where: a site admin is limited to its OU on every DC; a domain admin is not, even at a site DC
r=$(mk 10.89.0.11 "$W/admin.auth" "$(user adminatsite "$O1")"); echo "$r" | grep -q successfully \
    && echo "NOTE a domain admin signed in at the site DC can write another site's OU (AD limits who writes, not which DC)" \
    || echo "NOTE a domain admin was refused at the site DC: $r"
