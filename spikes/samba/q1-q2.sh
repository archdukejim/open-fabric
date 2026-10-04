#!/bin/bash
# S0 spike Q1 (a hardened DC) and Q2 (BIND serving the AD zone through DLZ). Fresh domain each run.
#   sudo bash spikes/samba/q1-q2.sh
. "$(dirname "$0")/common.sh"
clean_all; mkdir -p "$W/secrets"
build_images && echo "images built"
start_dc; start_bind
echo "--- Q1"
echo "DC: $(docker ps -a --filter name=s0-dc --format '{{.Status}}'), memory $(docker stats --no-stream --format '{{.MemUsage}}' s0-dc)"
auth_file Administrator "$W/secrets/admin_password" "$W/admin.auth"
client -v "$W/admin.auth:/auth:ro" -- smbclient //"$DC_IP"/netlogon -A /auth -c ls >/dev/null 2>&1 \
    && echo "PASS SMB sign-in as the administrator (password from a file)" || echo "FAIL SMB sign-in"
client -v "$W/admin.auth:/auth:ro" -- ldbsearch -H "ldap://$DC_IP" -A /auth -b "$B" "(sAMAccountName=Administrator)" dn \
    2>/dev/null | grep -q "^dn: CN=Administrator" && echo "PASS LDAP lookup" || echo "FAIL LDAP lookup"
CAPS="SETGID" start_dc
client -v "$W/admin.auth:/auth:ro" -- smbclient //"$DC_IP"/netlogon -A /auth -c ls >/dev/null 2>&1 \
    && echo "PASS restarted on the same domain with only SETGID (re-run converges)" || echo "FAIL restart with SETGID only"
start_bind
echo "--- Q2"
client -- dig +short @"$DC_IP" SRV _ldap._tcp.ad.lan.test | grep -q "389 dc1.ad.lan.test" \
    && echo "PASS BIND answers the AD zone (DLZ)" || echo "FAIL AD zone"
client -- dig +short @"$DC_IP" SOA ad.lan.test | grep -q "^dc1.ad.lan.test." \
    && echo "PASS the AD zone's SOA names the DC by its full name" || echo "FAIL SOA"
docker exec s0-dc samba_dnsupdate -s /data/etc/smb.conf --all-names 2>&1 | grep -q "Failed update" \
    && echo "FAIL signed updates" || echo "PASS signed (GSS-TSIG) updates from the DC through BIND"
printf 'server %s\nzone ad.lan.test\nupdate add evil.ad.lan.test 60 A 10.88.0.66\nsend\n' "$DC_IP" > "$W/upd"
client -v "$W/upd:/upd:ro" -- nsupdate /upd 2>&1 | grep -q REFUSED && echo "PASS an unsigned update is refused" \
    || echo "FAIL unsigned update not refused"
