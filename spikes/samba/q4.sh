#!/bin/bash
# S0 spike Q4: per-site delegation (decision S2). An OU per site; house2's admins get rights on their OU only.
# Needs the DC of q1-q2.sh running.   sudo bash spikes/samba/q4.sh
. "$(dirname "$0")/common.sh"
C=(-s /data/etc/smb.conf)
dx() { docker exec s0-dc "$@"; }
dx samba-tool ou create "OU=sites,$B" "${C[@]}" >/dev/null 2>&1
for s in house1 house2; do dx samba-tool ou create "OU=$s,OU=sites,$B" "${C[@]}" >/dev/null 2>&1; done
dx samba-tool group add house2-admins --groupou="OU=house2,OU=sites" "${C[@]}" >/dev/null 2>&1
dx samba-tool user create h2admin --random-password --userou="OU=house2,OU=sites" "${C[@]}" >/dev/null 2>&1
new_password "$W/secrets/h2admin"
docker exec -i s0-dc sh -c "umask 077; cat > /tmp/pw" < "$W/secrets/h2admin"
dx python3 /usr/local/bin/setpass.py /data/etc/smb.conf h2admin /tmp/pw >/dev/null 2>&1; dx rm -f /tmp/pw
dx samba-tool group addmembers house2-admins h2admin "${C[@]}" >/dev/null 2>&1
sid=$(dx ldbsearch -H /data/private/sam.ldb "(sAMAccountName=house2-admins)" objectSid | sed -n 's/^objectSid: //p')
# read, write, create and delete children, list, read and change permissions: inherited below the OU only
dx samba-tool dsacl set --objectdn="OU=house2,OU=sites,$B" --sddl="(A;CI;RPWPCRCCDCLCLORCWOWDSDDTSW;;;$sid)" \
    "${C[@]}" >/dev/null && echo "delegated OU=house2 to house2-admins ($sid)"
auth_file h2admin "$W/secrets/h2admin" "$W/h2.auth"
ldif() {  # tool ldif-text -> last line of the tool's output, run as h2admin
    printf '%b' "$2" > "$W/op.ldif"
    client -v "$W/h2.auth:/auth:ro" -v "$W/op.ldif:/op.ldif:ro" -- "$1" -H "ldap://$DC_IP" -A /auth /op.ldif 2>&1 | tail -1
}
user() { printf 'dn: CN=%s,%s\nobjectClass: user\nsAMAccountName: %s\n' "$1" "$2" "$1"; }
r=$(ldif ldbadd "$(user h2user "OU=house2,OU=sites,$B")"); echo "$r" | grep -q successfully \
    && echo "PASS a site admin adds a user in its own site" || echo "FAIL own site add: $r"
r=$(ldif ldbadd "$(user h2evil "OU=house1,OU=sites,$B")"); echo "$r" | grep -q failed \
    && echo "PASS refused in another site" || echo "FAIL another site: $r"
r=$(ldif ldbadd "$(user h2evil2 "CN=Users,$B")"); echo "$r" | grep -q failed \
    && echo "PASS refused at the domain level" || echo "FAIL domain level: $r"
r=$(ldif ldbmodify "dn: CN=Administrator,CN=Users,$B\nchangetype: modify\nreplace: description\ndescription: owned\n")
echo "$r" | grep -q failed && echo "PASS refused on the domain's administrator" || echo "FAIL administrator: $r"
r=$(ldif ldbmodify "dn: CN=h2user,OU=house2,OU=sites,$B\nchangetype: delete\n"); echo "$r" | grep -q successfully \
    && echo "PASS a site admin removes its own site's user" || echo "FAIL own site delete: $r"
echo "--- Q5"
dx samba-tool domain join x SUBDOMAIN 2>&1 | grep -q "possible values: MEMBER, DC, RODC" \
    && echo "PASS confirmed: samba-tool joins only as MEMBER, DC or RODC — no child domains (one domain per forest)"
