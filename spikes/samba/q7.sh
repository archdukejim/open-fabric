#!/bin/bash
# S0 spike Q7: Keycloak with AD as its user store (LDAP provider, AD mode, writable). Needs the DC of q1-q2.sh and
# the site OUs of q4.sh. Secrets go through files and the environment, never argv.   sudo bash spikes/samba/q7.sh
. "$(dirname "$0")/common.sh"
KC_IMAGE=keycloak/keycloak:26.7.4@sha256:82a77884f3af238beab1e7afd63b5f530e1b5c0590bd7aa60b40a40463e29b2c
dx() { docker exec s0-dc "$@"; }
setpw() {  # user password-file
    docker exec -i s0-dc sh -c "umask 077; cat > /tmp/pw" < "$2"
    dx python3 /usr/local/bin/setpass.py /data/etc/smb.conf "$1" /tmp/pw >/dev/null 2>&1; dx rm -f /tmp/pw
}
echo "--- Q7"
dx samba-tool user create alice --random-password --userou="OU=house2,OU=sites" --given-name=Alice --surname=Lee \
    --mail-address=alice@lan.test -s /data/etc/smb.conf >/dev/null 2>&1
new_password "$W/secrets/alice"; setpw alice "$W/secrets/alice"
new_password "$W/secrets/kc_admin"
sudo cp "$W/data/private/tls/ca.pem" "$W/dc-ca.pem"; sudo chmod 644 "$W/dc-ca.pem"
docker rm -f s0-kc >/dev/null 2>&1
docker run -d --name s0-kc --network s0net --ip 10.88.0.60 --add-host dc1.ad.lan.test:"$DC_IP" --memory 1200m \
    --cap-drop ALL --security-opt no-new-privileges:true \
    -e KC_BOOTSTRAP_ADMIN_USERNAME=admin -e KC_BOOTSTRAP_ADMIN_PASSWORD="$(cat "$W/secrets/kc_admin")" \
    -e KC_TRUSTSTORE_PATHS=/dc-ca.pem -v "$W/dc-ca.pem:/dc-ca.pem:ro" "$KC_IMAGE" start-dev >/dev/null
for _ in $(seq 1 90); do docker logs s0-kc 2>&1 | grep -q "Listening on" && break; sleep 2; done
kc() { docker exec -e KC_CLI_PASSWORD="$(cat "$W/secrets/kc_admin")" s0-kc /opt/keycloak/bin/kcadm.sh "$@"; }
kc config credentials --server http://localhost:8080 --realm master --user admin >/dev/null 2>&1
kc create realms -s realm=spike -s enabled=true >/dev/null 2>&1
kc create clients -r spike -s clientId=probe -s publicClient=true -s directAccessGrantsEnabled=true >/dev/null 2>&1
# the LDAP provider, from a 0600 file (its bind password must not be on a command line)
(umask 077; cat > "$W/ldap.json" <<JSON
{"name": "ad", "providerId": "ldap", "providerType": "org.keycloak.storage.UserStorageProvider",
 "config": {"vendor": ["ad"], "editMode": ["WRITABLE"], "enabled": ["true"],
  "connectionUrl": ["ldaps://dc1.ad.lan.test:636"], "usersDn": ["OU=sites,$B"],
  "bindDn": ["CN=Administrator,CN=Users,$B"], "bindCredential": ["$(cat "$W/secrets/admin_password")"],
  "usernameLDAPAttribute": ["sAMAccountName"], "rdnLDAPAttribute": ["cn"], "uuidLDAPAttribute": ["objectGUID"],
  "userObjectClasses": ["person, organizationalPerson, user"], "searchScope": ["2"],
  "authType": ["simple"], "useTruststoreSpi": ["always"], "pagination": ["true"]}}
JSON
)
docker exec -i s0-kc sh -c "cat > /tmp/ldap.json" < "$W/ldap.json"
kc create components -r spike -f /tmp/ldap.json >/dev/null 2>&1 && echo "PASS Keycloak's AD provider created (LDAPS, the DC's CA trusted)" \
    || echo "FAIL AD provider"
docker exec s0-kc rm -f /tmp/ldap.json
token() {  # user password-file -> HTTP status of a password grant
    docker run --rm --network s0net --user 0 -v "$2:/pw:ro" --entrypoint sh \
        curlimages/curl:8.11.1@sha256:c1fe1679c34d9784c1b0d1e5f62ac0a79fca01fb6377cdd33e90473c6f9f9a69 -c \
        "curl -s -o /dev/null -w '%{http_code}' http://10.88.0.60:8080/realms/spike/protocol/openid-connect/token \
         -d grant_type=password -d client_id=probe -d username=$1 --data-urlencode password@/pw"
}
[ "$(token alice "$W/secrets/alice")" = 200 ] && echo "PASS an AD user signs in through Keycloak (password checked by AD)" \
    || echo "FAIL AD user sign-in through Keycloak"
new_password "$W/secrets/wrong"
r=$(token alice "$W/secrets/wrong"); [ "$r" = 400 ] || [ "$r" = 401 ] \
    && echo "PASS a wrong password is refused (HTTP $r, invalid_grant)" || echo "FAIL wrong password: HTTP $r"
# a new password set in Keycloak (admin reset) lands in AD
new_password "$W/secrets/alice2"
uid=$(kc get users -r spike -q username=alice --fields id 2>/dev/null | sed -n 's/.*"id" : "\(.*\)".*/\1/p')
printf '{"type": "password", "temporary": false, "value": "%s"}' "$(cat "$W/secrets/alice2")" \
    | docker exec -i s0-kc sh -c "umask 077; cat > /tmp/pw.json"
kc update "users/$uid/reset-password" -r spike -f /tmp/pw.json >/dev/null 2>&1; docker exec s0-kc rm -f /tmp/pw.json
auth_file alice "$W/secrets/alice2" "$W/alice2.auth"; auth_file alice "$W/secrets/alice" "$W/alice.auth"
client -v "$W/alice2.auth:/auth:ro" -- smbclient //"$DC_IP"/netlogon -A /auth -c ls >/dev/null 2>&1 \
    && echo "PASS a password set in Keycloak works for an AD (SMB) sign-in" || echo "FAIL password from Keycloak not in AD"
[ "$(token alice "$W/secrets/alice2")" = 200 ] && echo "PASS the new password signs in through Keycloak" \
    || echo "FAIL the new password through Keycloak"
# AD keeps accepting the previous password for network sign-ins for a while ("old password allowed period")
period=$(dx testparm -s /data/etc/smb.conf --parameter-name="old password allowed period" 2>/dev/null)
client -v "$W/alice.auth:/auth:ro" -- smbclient //"$DC_IP"/netlogon -A /auth -c ls >/dev/null 2>&1 \
    && echo "NOTE the old password still works for $period minutes after a change (Samba's old password allowed period)" \
    || echo "NOTE the old password stopped working at once"
dx samba-tool user disable alice -s /data/etc/smb.conf >/dev/null 2>&1
r=$(token alice "$W/secrets/alice2"); [ "$r" = 400 ] || [ "$r" = 401 ] \
    && echo "PASS a user disabled in AD is refused by Keycloak (HTTP $r)" || echo "FAIL disabled user: HTTP $r"
dx samba-tool user enable alice -s /data/etc/smb.conf >/dev/null 2>&1
echo "Keycloak memory: $(docker stats --no-stream --format '{{.MemUsage}}' s0-kc) (dev mode, H2)"
