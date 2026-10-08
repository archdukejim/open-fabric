#!/bin/bash
# S0 spike Q9: a Linux machine (Ubuntu 24.04) joins AD into its site's OU; identities (fabric's POSIX ids), Kerberos,
# access by group and sudo rules come from AD through SSSD. Needs q1-q2.sh, q4.sh and q7.sh (alice).
#   sudo bash spikes/samba/q9.sh
. "$(dirname "$0")/common.sh"
dx() { docker exec s0-dc "$@"; }
C=(-s /data/etc/smb.conf)
OU="OU=house2,OU=sites"
echo "--- Q9"
docker build -q -t s0/client "$HERE/client" >/dev/null && echo "client image built"
# sudo's schema into AD (two sessions, as fabric's)
for part in attributes classes; do
    python3 "$HERE/ad-schema.py" "$B" sudo "$part" | docker exec -i s0-dc sh -c "cat > /tmp/sudo-$part.ldif"
    dx ldbmodify -H /data/private/sam.ldb --option="dsdb:schema update allowed=true" "/tmp/sudo-$part.ldif" 2>&1 \
        | grep -qE "successfully|already exists" || echo "FAIL sudo schema $part"
done
# fabric's POSIX ids (RFC 2307): a group allowed on Linux machines, alice in it, bob not
dx samba-tool group add linux-admins --groupou="$OU" --nis-domain=lan --gid-number=20000 "${C[@]}" >/dev/null 2>&1
dx samba-tool group add linux-users --groupou="$OU" --nis-domain=lan --gid-number=20001 "${C[@]}" >/dev/null 2>&1
dx samba-tool user create bob --random-password --userou="$OU" "${C[@]}" >/dev/null 2>&1
dx samba-tool user addunixattrs alice 20101 --gid-number=20000 --unix-home=/home/alice --login-shell=/bin/bash \
    "${C[@]}" >/dev/null 2>&1
dx samba-tool user addunixattrs bob 20102 --gid-number=20001 --unix-home=/home/bob --login-shell=/bin/bash \
    "${C[@]}" >/dev/null 2>&1
dx samba-tool group addmembers linux-admins alice "${C[@]}" >/dev/null 2>&1
dx samba-tool group addmembers linux-users bob "${C[@]}" >/dev/null 2>&1
printf 'dn: OU=sudoers,%s,%s\nobjectClass: organizationalUnit\n\ndn: CN=linux-admins-all,OU=sudoers,%s,%s\nobjectClass: sudoRole\nsudoUser: %%linux-admins\nsudoHost: ALL\nsudoCommand: ALL\n' \
    "$OU" "$B" "$OU" "$B" | docker exec -i s0-dc sh -c "cat > /tmp/sudo.ldif"
dx ldbadd -H /data/private/sam.ldb /tmp/sudo.ldif >/dev/null 2>&1
# the machine
docker rm -f s0-linux >/dev/null 2>&1
docker run -d --name s0-linux --hostname linux1.ad.lan.test --network s0net --ip 10.88.0.90 --dns "$DC_IP" \
    s0/client sleep infinity >/dev/null
lx() { docker exec s0-linux "$@"; }
lx sh -c 'printf "[libdefaults]\n default_realm = AD.LAN.TEST\n dns_lookup_kdc = true\n rdns = false\n" > /etc/krb5.conf'
docker exec -i s0-linux adcli join --domain=ad.lan.test --domain-ou="$OU,$B" --login-user=Administrator \
    --stdin-password < "$W/secrets/admin_password" >/dev/null 2>"$W/adcli.log" \
    && echo "PASS the machine joins AD into its site's OU (adcli; password on stdin)" \
    || { echo "FAIL join"; tail -5 "$W/adcli.log"; }
dx ldbsearch -H /data/private/sam.ldb -b "$OU,$B" "(sAMAccountName=LINUX1\$)" dn 2>/dev/null | grep -q "^dn: CN=LINUX1" \
    && echo "PASS its computer account is in the site's OU" || echo "FAIL computer account not in the site's OU"
docker exec -i s0-linux sh -c "umask 077; cat > /etc/sssd/sssd.conf" <<'CONF'
[sssd]
domains = ad.lan.test
services = nss, pam, sudo
[domain/ad.lan.test]
id_provider = ad
access_provider = simple
simple_allow_groups = linux-admins
sudo_provider = ad
ldap_id_mapping = false
use_fully_qualified_names = false
fallback_homedir = /home/%u
CONF
lx sh -c 'sssd -i --logger=stderr > /var/log/sssd.out 2>&1 &'; sleep 8
lx getent passwd alice | grep -q ":20101:20000:" && echo "PASS identities from AD with fabric's ids (alice 20101:20000)" \
    || echo "FAIL identity: $(lx getent passwd alice)"
lx id alice | grep -q "linux-admins" && echo "PASS group membership from AD" || echo "FAIL groups: $(lx id alice)"
docker exec -i s0-linux sh -c "kinit alice@AD.LAN.TEST >/dev/null 2>&1 && klist | grep -q krbtgt/" < "$W/secrets/alice2" \
    && echo "PASS Kerberos on the machine (kinit alice)" || echo "FAIL kinit on the machine"
lx sssctl user-checks alice -a acct 2>&1 | grep -q "pam_acct_mgmt: Success" \
    && echo "PASS alice (linux-admins) may log in" || echo "FAIL alice access"
lx sssctl user-checks bob -a acct 2>&1 | grep -q "pam_acct_mgmt: Success" \
    && echo "FAIL bob (not in linux-admins) may log in" || echo "PASS bob (not in the allowed group) is refused"
lx sudo -l -U alice 2>&1 | grep -qE '\((root|ALL)\) ALL' && echo "PASS sudo rule from AD for linux-admins" \
    || echo "FAIL sudo for alice: $(lx sudo -l -U alice 2>&1 | tail -2)"
lx sudo -l -U bob 2>&1 | grep -qE '\((root|ALL)\) ALL' && echo "FAIL bob got sudo" || echo "PASS no sudo for bob"
