#!/bin/bash
# S0 spike Q8: 802.1X PEAP-MSCHAPv2 for a person and a machine, checked by AD through the DC's winbind
# (ntlm_auth), with FreeRADIUS non-root (uid 610) in its own hardened container. Needs q1-q2.sh, q4.sh and q7.sh
# (the user alice).   sudo bash spikes/samba/q8.sh
. "$(dirname "$0")/common.sh"
dx() { docker exec s0-dc "$@"; }
echo "--- Q8"
build_images && docker build -q -t s0/radius "$HERE/radius" >/dev/null && echo "images built"
CAPS="SETGID SETUID" start_dc; start_bind
# FreeRADIUS (gid 610) may use winbind's privileged pipe for ntlm_auth. Samba checks only the folder's owner and
# mode (root, 0750), so its group is set from the host, as fabric's deploy (root) would; the DC has no CHOWN at run time
sudo chgrp 610 "$W/data/state/winbindd_privileged" && sudo chmod 0750 "$W/data/state/winbindd_privileged"
echo "winbind's privileged pipe: $(sudo stat -c '%u:%g %a' "$W/data/state/winbindd_privileged")"
sslcert=$(docker run --rm --entrypoint getent s0/radius group ssl-cert | cut -d: -f3)
# a computer account with a known password stands in for a Windows machine
dx samba-tool computer create ws1 -s /data/etc/smb.conf >/dev/null 2>&1
new_password "$W/secrets/ws1"
docker exec -i s0-dc sh -c "umask 077; cat > /tmp/pw" < "$W/secrets/ws1"
dx python3 /usr/local/bin/setpass.py /data/etc/smb.conf 'ws1$' /tmp/pw >/dev/null 2>&1; dx rm -f /tmp/pw
new_password "$W/secrets/radius_secret"; sudo chown 610:610 "$W/secrets/radius_secret"
docker rm -f s0-radius >/dev/null 2>&1
docker run -d --name s0-radius --network s0net --ip 10.88.0.70 --user 610:610 --group-add "$sslcert" --cap-drop ALL \
    --security-opt no-new-privileges:true --read-only --tmpfs /tmp:size=8m \
    --tmpfs /run/freeradius:size=8m,uid=610,gid=610 --memory 128m \
    -v "$W/winbindd:/run/samba/winbindd:ro" -v "$W/data/state/winbindd_privileged:/data/state/winbindd_privileged:ro" \
    -v "$W/data/etc/smb.conf:/etc/samba/smb.conf:ro" -v "$W/secrets/radius_secret:/run/secrets/radius_secret:ro" \
    --entrypoint /usr/local/bin/radius.sh s0/radius >/dev/null
sleep 6
docker ps --filter name=s0-radius --format '{{.Status}}' | grep -q Up \
    && echo "PASS FreeRADIUS runs as uid 610, no capabilities, read-only root" \
    || { echo "FAIL FreeRADIUS did not start"; docker logs s0-radius 2>&1 | tail -8; exit 1; }
peap() {  # identity password-file -> 0 when eapol_test gets Access-Accept
    (umask 077; printf 'network={\n key_mgmt=WPA-EAP\n eap=PEAP\n identity="%s"\n password="%s"\n phase2="auth=MSCHAPV2"\n}\n' \
        "$1" "$(cat "$2")" > "$W/eap.conf")
    docker run --rm --network s0net -v "$W/eap.conf:/eap.conf:ro" --entrypoint eapol_test s0/radius \
        -c /eap.conf -a 10.88.0.70 -s "$(cat "$W/secrets/radius_secret")" > "$W/eapol.log" 2>&1
    grep -q "^SUCCESS" "$W/eapol.log"
}
peap alice "$W/secrets/alice2" && echo "PASS PEAP-MSCHAPv2 for a person (password checked by AD)" \
    || { echo "FAIL PEAP for a person"; docker logs s0-radius 2>&1 | grep -iE "ntlm_auth|mschap|reject" | tail -5; }
peap alice "$W/secrets/wrong" && echo "FAIL a wrong password was accepted" || echo "PASS PEAP with a wrong password refused"
peap host/ws1.ad.lan.test "$W/secrets/ws1" && echo "PASS PEAP machine authentication (host/ws1 -> ws1\$ in AD)" \
    || { echo "FAIL PEAP for a machine"; docker logs s0-radius 2>&1 | grep -iE "ntlm_auth|mschap|reject" | tail -5; }
dx samba-tool user disable alice -s /data/etc/smb.conf >/dev/null 2>&1
peap alice "$W/secrets/alice2" && echo "FAIL a disabled account was accepted" || echo "PASS PEAP for a disabled account refused"
dx samba-tool user enable alice -s /data/etc/smb.conf >/dev/null 2>&1
echo "FreeRADIUS memory: $(docker stats --no-stream --format '{{.MemUsage}}' s0-radius)"
