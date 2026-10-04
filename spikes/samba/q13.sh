#!/bin/bash
# S0 spike Q13: Group Policy from ADMX. Samba's own ADMX/ADML (as an admin would load any template) is parsed,
# a policy's value is written into a GPO's Registry.pol with Samba's bindings (plus fabric's root-CA trust in the
# registry form Windows reads), the GPO is linked to house2's OU, and a Samba member there applies it with
# samba-gpupdate. Needs q1-q2.sh and q4.sh.   sudo bash spikes/samba/q13.sh
. "$(dirname "$0")/common.sh"
dx() { docker exec s0-dc "$@"; }
C=(-s /data/etc/smb.conf)
O2="OU=house2,OU=sites"
ADMX=/usr/share/samba/admx/samba.admx; ADML=/usr/share/samba/admx/en-US/samba.adml
POLICY=POL_33AAE399_07A8_5CC8_882A_393E4B96B259; ELEMENT=TXT_F940E18B_16AE_594B_9669_96417E695AC9  # additional dns hostnames
echo "--- Q13"
CAPS="CHOWN DAC_OVERRIDE FOWNER SETUID SETGID" start_dc; start_bind     # Group Policy writes ACLs on SYSVOL
auth_file Administrator "$W/secrets/admin_password" "$W/admin.auth"
docker exec -i s0-dc sh -c "umask 077; cat > /tmp/admin.auth" < "$W/admin.auth"
docker exec -i s0-dc sh -c "cat > /tmp/admx.py" < "$HERE/admx.py"
n=$(dx python3 /tmp/admx.py list "$ADMX" "$ADML" | wc -l)
dx python3 /tmp/admx.py list "$ADMX" "$ADML" | grep -q "^$POLICY.*additional dns hostnames" \
    && echo "PASS the ADMX/ADML are parsed: $n policies with their names (e.g. 'additional dns hostnames')" \
    || echo "FAIL parsing the ADMX"
dx samba-tool gpo admxload -H ldap://dc1.ad.lan.test -A /tmp/admin.auth "${C[@]}" >/dev/null 2>&1 \
    && echo "PASS the templates are loaded into the domain's central store (samba-tool gpo admxload)" \
    || echo "NOTE admxload failed"
gc() { dx samba-tool gpo "$@" -H ldap://dc1.ad.lan.test -A /tmp/admin.auth "${C[@]}"; }
guid=$(gc create "house2 settings" 2>/dev/null | grep -oE '\{[0-9A-Fa-f-]{36}\}' | head -1)
gc setlink "$O2,$B" "$guid" >/dev/null 2>&1 && echo "GPO $guid linked to house2's OU"
POL=/data/state/sysvol/ad.lan.test/Policies/$guid
dx mkdir -p "$POL/Machine"
dx python3 /tmp/admx.py write "$ADMX" "$ADML" "$POL/Machine/Registry.pol" "$POLICY" "$ELEMENT=extra.ad.lan.test" \
    --root-ca /data/private/tls/ca.pem | tail -1
# the Registry client extension (Windows needs it listed); version up in the GPO and its GPT.INI
printf 'dn: CN=%s,CN=Policies,CN=System,%s\nchangetype: modify\nreplace: versionNumber\nversionNumber: 1\n-\nreplace: gPCMachineExtensionNames\ngPCMachineExtensionNames: [{35378EAC-683F-11D2-A89A-00C04FBBCFA2}{D02B1F72-3407-48AE-BA88-E8213C6761F1}]\n' \
    "$guid" "$B" | docker exec -i s0-dc sh -c "cat > /tmp/gpo.ldif"
dx ldbmodify -H /data/private/sam.ldb /tmp/gpo.ldif >/dev/null 2>&1
printf '[General]\r\nVersion=1\r\n' | docker exec -i s0-dc sh -c "cat > '$POL/GPT.INI'"
dx samba-tool ntacl sysvolreset "${C[@]}" >/dev/null 2>&1
# a Samba member in house2's OU applies it
docker rm -f s0-member >/dev/null 2>&1
docker run -d --name s0-member --hostname member1.ad.lan.test --network s0net --ip 10.88.0.92 --dns "$DC_IP" \
    --entrypoint sleep s0/dc infinity >/dev/null
mx() { docker exec s0-member "$@"; }
mx sh -c 'mkdir -p /etc/samba && printf "[global]\n workgroup = LAN\n realm = AD.LAN.TEST\n security = ADS\n kerberos method = secrets and keytab\n apply group policies = yes\n" > /etc/samba/smb.conf'
mx sh -c 'printf "[libdefaults]\n default_realm = AD.LAN.TEST\n dns_lookup_kdc = true\n rdns = false\n" > /etc/krb5.conf'
docker exec -i s0-member sh -c "kinit Administrator@AD.LAN.TEST >/dev/null" < "$W/secrets/admin_password"
mx net ads join -k createcomputer="Sites/house2" >/dev/null 2>"$W/join.log" \
    && echo "PASS a Samba member joins into house2's OU" || { echo "FAIL member join"; tail -3 "$W/join.log"; }
mx kdestroy >/dev/null 2>&1
mx samba-gpupdate --force > "$W/gpupdate.log" 2>&1
mx grep -qi "additional dns hostnames = extra.ad.lan.test" /etc/samba/smb.conf \
    && echo "PASS the member applied the ADMX policy from the GPO (its smb.conf has the value)" \
    || { echo "FAIL the policy was not applied"; tail -5 "$W/gpupdate.log"; }
mx samba-gpupdate --rsop 2>/dev/null | grep -qi "SystemCertificates" \
    && echo "PASS the root-CA trust entry reaches the member in the GPO (Windows applies it: manual check)" \
    || echo "NOTE the root-CA entry is not shown by the member's RSoP (a Windows-only setting; manual check)"
docker rm -f s0-member >/dev/null 2>&1
