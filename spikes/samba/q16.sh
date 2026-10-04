#!/bin/bash
# S0 spike Q16: per-site logon rights (D90). A GPO on site house2's OU allows log-on (local and remote) to
# house2-users only; a house2 Linux machine enforces it through SSSD (ad_gpo_access_control). A house1 person is
# refused until allowed explicitly; a blanket policy allows everyone. Needs q1-q2.sh and q4.sh (the DC and site OUs).
#   sudo bash spikes/samba/q16.sh
. "$(dirname "$0")/common.sh"
dx() { docker exec s0-dc "$@"; }
C=(-s /data/etc/smb.conf)
O1="OU=house1,OU=sites"; O2="OU=house2,OU=sites"
echo "--- Q16"
# Group Policy writes Windows ACLs on SYSVOL's files: the DC needs CHOWN, FOWNER and DAC_OVERRIDE besides SETUID/SETGID
CAPS="CHOWN DAC_OVERRIDE FOWNER SETUID SETGID" start_dc; start_bind
auth_file Administrator "$W/secrets/admin_password" "$W/admin.auth"
docker build -q -t s0/client "$HERE/client" >/dev/null
# people and groups of two sites, with POSIX ids
dx samba-tool group add house1-users --groupou="$O1" --nis-domain=lan --gid-number=21001 "${C[@]}" >/dev/null 2>&1
dx samba-tool group add house2-users --groupou="$O2" --nis-domain=lan --gid-number=21002 "${C[@]}" >/dev/null 2>&1
dx samba-tool user create h1person --random-password --userou="$O1" "${C[@]}" >/dev/null 2>&1
dx samba-tool user create h2person --random-password --userou="$O2" "${C[@]}" >/dev/null 2>&1
dx samba-tool user addunixattrs h1person 21101 --gid-number=21001 --unix-home=/home/h1person --login-shell=/bin/bash "${C[@]}" >/dev/null 2>&1
dx samba-tool user addunixattrs h2person 21102 --gid-number=21002 --unix-home=/home/h2person --login-shell=/bin/bash "${C[@]}" >/dev/null 2>&1
dx samba-tool group addmembers house1-users h1person "${C[@]}" >/dev/null 2>&1
dx samba-tool group addmembers house2-users h2person "${C[@]}" >/dev/null 2>&1
sid() { dx ldbsearch -H /data/private/sam.ldb "(sAMAccountName=$1)" objectSid 2>/dev/null | sed -n 's/^objectSid: //p'; }
H2SID=$(sid house2-users)
# the GPO, linked to house2's OU
# run on the DC (a bare client cannot locate the DC over CLDAP); the administrator's credentials go in on stdin
docker exec -i s0-dc sh -c "umask 077; cat > /tmp/admin.auth" < "$W/admin.auth"
gc() { dx samba-tool gpo "$@" -H ldap://dc1.ad.lan.test -A /tmp/admin.auth "${C[@]}"; }
guid=$(gc create "house2 logon rights" 2>/dev/null | grep -oE '\{[0-9A-Fa-f-]{36}\}' | head -1)
[ -n "$guid" ] && gc setlink "$O2,$B" "$guid" >/dev/null 2>&1 && echo "GPO $guid linked to house2's OU"
POL=/data/state/sysvol/ad.lan.test/Policies/$guid
write_rights() {  # SIDs allowed to log on (local and remote): GptTmpl.inf as Windows writes it (UTF-16LE), version up
    local sids="*$1"; shift; for s in "$@"; do sids="$sids,*$s"; done
    printf '[Unicode]\r\nUnicode=yes\r\n[Version]\r\nsignature="$CHICAGO$"\r\nRevision=1\r\n[Privilege Rights]\r\nSeInteractiveLogonRight = %s\r\nSeRemoteInteractiveLogonRight = %s\r\n' \
        "$sids" "$sids" | iconv -f utf-8 -t utf-16 > "$W/GptTmpl.inf"
    docker exec s0-dc mkdir -p "$POL/Machine/Microsoft/Windows NT/SecEdit"
    docker exec -i s0-dc sh -c "cat > '$POL/Machine/Microsoft/Windows NT/SecEdit/GptTmpl.inf'" < "$W/GptTmpl.inf"
    ver=$(( $(dx ldbsearch -H /data/private/sam.ldb -b "CN=$guid,CN=Policies,CN=System,$B" -s base versionNumber 2>/dev/null \
          | sed -n 's/^versionNumber: //p') + 1 ))
    printf 'dn: CN=%s,CN=Policies,CN=System,%s\nchangetype: modify\nreplace: versionNumber\nversionNumber: %s\n-\nreplace: gPCMachineExtensionNames\ngPCMachineExtensionNames: [{827D319E-6EAC-11D2-A4EA-00C04F79F83A}{803E14A0-B4FB-11D0-A0D0-00A0C90F574B}]\n' \
        "$guid" "$B" "$ver" | docker exec -i s0-dc sh -c "cat > /tmp/gpo.ldif"
    dx ldbmodify -H /data/private/sam.ldb /tmp/gpo.ldif >/dev/null 2>&1
    printf '[General]\r\nVersion=%s\r\n' "$ver" | docker exec -i s0-dc sh -c "cat > '$POL/GPT.INI'"
    dx samba-tool ntacl sysvolreset "${C[@]}" >/dev/null 2>&1      # SYSVOL's ACLs after writing into it
}
write_rights "$H2SID"
# a house2 machine
docker rm -f s0-linux2 >/dev/null 2>&1
docker run -d --name s0-linux2 --hostname linux2.ad.lan.test --network s0net --ip 10.88.0.91 --dns "$DC_IP" \
    s0/client sleep infinity >/dev/null
lx() { docker exec s0-linux2 "$@"; }
lx sh -c 'printf "[libdefaults]\n default_realm = AD.LAN.TEST\n dns_lookup_kdc = true\n rdns = false\n" > /etc/krb5.conf'
docker exec -i s0-linux2 adcli join --domain=ad.lan.test --domain-ou="$O2,$B" --login-user=Administrator \
    --stdin-password < "$W/secrets/admin_password" >/dev/null 2>"$W/adcli2.log" || { echo "FAIL join"; tail -3 "$W/adcli2.log"; }
docker exec -i s0-linux2 sh -c "umask 077; cat > /etc/sssd/sssd.conf" <<'CONF'
[sssd]
domains = ad.lan.test
services = nss, pam
[domain/ad.lan.test]
id_provider = ad
access_provider = ad
ad_gpo_access_control = enforcing
ad_gpo_cache_timeout = 1
ldap_id_mapping = false
use_fully_qualified_names = false
CONF
lx sh -c 'sssd -i --logger=stderr > /var/log/sssd.out 2>&1 &'; sleep 10
may() {  # user -> 0 when SSSD lets the user log in over SSH (remote interactive)
    lx sss_cache -E >/dev/null 2>&1; sleep 2
    lx sssctl user-checks "$1" -a acct -s sshd 2>&1 | grep -q "pam_acct_mgmt: Success"
}
may h2person && echo "PASS a house2 person may log on to a house2 machine (the site's GPO)" || echo "FAIL house2 person refused"
may h1person && echo "FAIL a house1 person may log on at house2 without being allowed" \
    || echo "PASS a house1 person is refused at a house2 machine (not authorized there)"
# explicit: house1's person allowed at house2
write_rights "$H2SID" "$(sid h1person)"
may h1person && echo "PASS once allowed explicitly, the house1 person may log on at house2" || echo "FAIL explicit allow"
# blanket: everyone in the organisation (Domain Users)
write_rights "$H2SID" "$(sid 'Domain Users')"
dx samba-tool user create h3person --random-password "${C[@]}" >/dev/null 2>&1
dx samba-tool user addunixattrs h3person 21103 --gid-number=21001 --unix-home=/home/h3person --login-shell=/bin/bash "${C[@]}" >/dev/null 2>&1
may h3person && echo "PASS with the blanket policy (Domain Users) anyone in the organisation may log on at house2" \
    || echo "FAIL blanket policy"
may h2person && echo "NOTE the house2 person may log on now (after the first refusal)" || echo "NOTE the house2 person is still refused"
