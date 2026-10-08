#!/bin/bash
# S0 spike Q3 (fabric's data in AD's schema) and Q6 (a read-only DC at a site, working with the root DC stopped).
# Needs the DC of q1-q2.sh and the site OUs of q4.sh.   sudo bash spikes/samba/q3-q6.sh
. "$(dirname "$0")/common.sh"
dx() { docker exec s0-dc "$@"; }
auth_file Administrator "$W/secrets/admin_password" "$W/admin.auth"
ldap() {  # tool host ldif-text [auth] -> the tool's last line
    printf '%b' "$3" > "$W/op.ldif"
    client -v "${4:-$W/admin.auth}:/auth:ro" -v "$W/op.ldif:/op.ldif:ro" -- "$1" -H "ldap://$2" -A /auth /op.ldif 2>&1 \
        | tail -1
}
echo "--- Q3"
schema_ok=1
for part in attributes classes; do      # two sessions: the classes need the reloaded schema
    python3 "$HERE/ad-schema.py" "$B" fabric "$part" | docker exec -i s0-dc sh -c "cat > /tmp/$part.ldif"
    r=$(dx ldbmodify -H /data/private/sam.ldb --option="dsdb:schema update allowed=true" "/tmp/$part.ldif" 2>&1 \
        | tail -1)
    echo "$r" | grep -q successfully || { schema_ok=0; echo "FAIL schema $part: $r"; }
done
[ "$schema_ok" = 1 ] && echo "PASS fabric's 11 attributes and 4 classes added to AD's schema (OIDs from fabric's UUID)"
dx samba-tool dbcheck -s /data/etc/smb.conf --cross-ncs 2>&1 | tail -1 | grep -q "Checked .* objects (0 errors)" \
    && echo "PASS dbcheck: the directory is consistent after the schema change" || echo "FAIL dbcheck"
for ou in devices networks; do ldap ldbadd "$DC_IP" "dn: OU=$ou,OU=house2,OU=sites,$B\nobjectClass: organizationalUnit\n" >/dev/null; done
dev="dn: CN=printer1,OU=devices,OU=house2,OU=sites,$B\nobjectClass: device\nobjectClass: ieee802Device\n"
dev+="objectClass: fabricDevice\nobjectClass: fabricDeviceRoles\nmacAddress: 02:00:00:00:00:01\n"
dev+="fabricDeviceType: printer\nfabricEnabled: TRUE\nfabricRoleName: printers\n"
r=$(ldap ldbadd "$DC_IP" "$dev" "$W/h2.auth"); echo "$r" | grep -q successfully \
    && echo "PASS a site admin adds a device (device + ieee802Device + fabric's classes) in its site" \
    || echo "FAIL device: $r"
net="dn: CN=lan,OU=networks,OU=house2,OU=sites,$B\nobjectClass: fabricNetwork\nfabricCidr: 192.168.20.0/24\n"
net+="fabricSite: house2\nfabricVlan: 20\nfabricNetworkKind: lan\n"
r=$(ldap ldbadd "$DC_IP" "$net" "$W/h2.auth"); echo "$r" | grep -q successfully \
    && echo "PASS a site admin adds a network to the address plan" || echo "FAIL network: $r"
client -v "$W/admin.auth:/auth:ro" -- ldbsearch -H "ldap://$DC_IP" -A /auth -b "$B" "(fabricVlan=20)" fabricCidr \
    2>/dev/null | grep -q "fabricCidr: 192.168.20.0/24" && echo "PASS searched by a fabric attribute" \
    || echo "FAIL search"
r=$(ldap ldbadd "$DC_IP" "dn: CN=bad,OU=networks,OU=house2,OU=sites,$B\nobjectClass: fabricNetwork\n" "$W/h2.auth")
if [ "$schema_ok" = 1 ] && ! echo "$r" | grep -q successfully; then
    echo "PASS a network without its CIDR is refused (the schema's MUST)"
else echo "FAIL schema not enforced: $r"; fi

echo "--- Q6"
docker rm -f s0-dc2 >/dev/null 2>&1; sudo rm -rf "$W/data2"
docker run -d --name s0-dc2 --hostname dc2.ad.lan.test --network s0net --ip 10.88.0.11 --dns "$DC_IP" \
    --cap-drop ALL --cap-add CHOWN --cap-add DAC_OVERRIDE --cap-add FOWNER --cap-add SETUID --cap-add SETGID \
    --security-opt no-new-privileges:true --read-only --tmpfs /run:size=16m --tmpfs /tmp:size=64m \
    --tmpfs /var/log/samba:size=16m --memory 512m \
    -e REALM="$REALM" -e DOMAIN="$DOMAIN" -e HOST_IP=10.88.0.11 -e JOIN_ROLE=RODC -e JOIN_SERVER=dc1.ad.lan.test \
    -v "$W/data2:/data" -v "$W/admin.auth:/run/secrets/join.auth:ro" s0/dc >/dev/null
for _ in $(seq 1 90); do docker logs s0-dc2 2>&1 | grep -qE "Starting process|^ERROR|Exited" && break; sleep 2; done; sleep 10
docker logs s0-dc2 2>&1 | grep -q "^joined" && echo "PASS an RODC joins the domain (hardened like the DC)" \
    || { echo "FAIL RODC join"; docker logs s0-dc2 2>&1 | tail -8; exit 1; }
docker exec s0-dc2 ldbsearch -H /data/private/sam.ldb -b "$B" "(cn=printer1)" fabricDeviceType \
    2>/dev/null | grep -q "fabricDeviceType: printer" \
    && echo "PASS the device and fabric's schema replicated to the RODC" || echo "FAIL replication to the RODC"
dx samba-tool group addmembers "Allowed RODC Password Replication Group" h2admin -s /data/etc/smb.conf >/dev/null
docker exec s0-dc2 samba-tool rodc preload h2admin -s /data/etc/smb.conf --server=dc1.ad.lan.test >/dev/null 2>&1
# Kerberos against the RODC's KDC only (MIT kinit; password on stdin from its file)
printf '[libdefaults]\n default_realm = %s\n dns_lookup_kdc = false\n rdns = false\n[realms]\n %s = {\n  kdc = 10.88.0.11\n }\n' \
    "$REALM" "$REALM" > "$W/krb5-rodc.conf"
kinit_rodc() {  # user password-file -> 0 when the RODC's KDC hands out a ticket
    client -e KRB5_CONFIG=/krb5.conf -v "$W/krb5-rodc.conf:/krb5.conf:ro" -v "$2:/pw:ro" -- \
        sh -c "kinit $1@$REALM < /pw >/dev/null 2>&1 && klist | grep -q krbtgt/"
}
kinit_rodc Administrator "$W/secrets/admin_password" \
    && echo "PASS Kerberos at the RODC for an account it does not cache (forwarded to the root DC)" \
    || echo "FAIL Kerberos forwarding at the RODC"
client -v "$W/admin.auth:/auth:ro" -- ldbsearch -H ldap://10.88.0.11 -A /auth -b "$B" "(sAMAccountName=h2admin)" cn \
    2>/dev/null | grep -q "^cn: h2admin" && echo "NOTE NTLM at the RODC is forwarded for uncached accounts" \
    || echo "NOTE NTLM at the RODC is not forwarded for an account it does not cache (finding for Q8, PEAP)"
docker stop s0-dc >/dev/null; echo "(the root DC is stopped)"
kinit_rodc h2admin "$W/secrets/h2admin" && echo "PASS Kerberos for a cached site user with the root DC down" \
    || echo "FAIL Kerberos for a cached user with the root DC down"
kinit_rodc Administrator "$W/secrets/admin_password" \
    && echo "FAIL Kerberos for the administrator with the root DC down (must never be cached)" \
    || echo "PASS Kerberos for the administrator refused with the root DC down"
client -v "$W/h2.auth:/auth:ro" -- ldbsearch -H ldap://10.88.0.11 -A /auth -b "$B" "(sAMAccountName=h2admin)" cn 2>/dev/null \
    | grep -q "^cn: h2admin" && echo "PASS a site user signs in at the RODC with the root DC down (cached password)" \
    || echo "FAIL cached sign-in at the RODC"
client -v "$W/admin.auth:/auth:ro" -- ldbsearch -H ldap://10.88.0.11 -A /auth -b "$B" "(sAMAccountName=h2admin)" cn 2>/dev/null | grep -q "^cn: h2admin" \
    && echo "FAIL the administrator signed in at the RODC (its password must never be cached)" \
    || echo "PASS the administrator's password is not on the RODC: refused with the root DC down"
r=$(ldap ldbmodify 10.88.0.11 "dn: CN=printer1,OU=devices,OU=house2,OU=sites,$B\nchangetype: modify\nreplace: fabricEnabled\nfabricEnabled: FALSE\n" "$W/h2.auth")
echo "$r" | grep -q successfully && echo "FAIL a write was accepted at the RODC" || echo "PASS the RODC refuses writes"
docker start s0-dc >/dev/null; sleep 15; start_bind; echo "(the root DC and BIND are back)"
echo "RODC memory: $(docker stats --no-stream --format '{{.MemUsage}}' s0-dc2)"
