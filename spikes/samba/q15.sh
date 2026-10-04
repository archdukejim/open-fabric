#!/bin/bash
# S0 spike Q15: change a site DC's type — writable -> read-only -> writable — by demoting it and joining again under
# the same name. Needs q12.sh's writable site DC (s0-dc2).   sudo bash spikes/samba/q15.sh
. "$(dirname "$0")/common.sh"
C=(-s /data/etc/smb.conf)
echo "--- Q15"
uac() {  # the DC's account flags as the root DC sees them
    docker exec s0-dc ldbsearch -H /data/private/sam.ldb -b "$B" "(sAMAccountName=DC2\$)" userAccountControl 2>/dev/null \
        | sed -n 's/^userAccountControl: //p'
}
kind() {  # writable (SERVER_TRUST_ACCOUNT) or read-only (PARTIAL_SECRETS_ACCOUNT), from the account flags
    local u; u=$(uac)
    if [ -z "$u" ]; then echo none; elif [ $((u & 0x4000000)) -ne 0 ]; then echo read-only
    elif [ $((u & 0x2000)) -ne 0 ]; then echo writable; else echo "other ($u)"; fi
}
rejoin() {  # role
    docker exec s0-dc2 samba-tool domain demote "${C[@]}" -A /run/secrets/join.auth --server=dc1.ad.lan.test \
        > "$W/demote.log" 2>&1 || { echo "FAIL demote"; tail -5 "$W/demote.log"; return 1; }
    docker rm -f s0-dc2 >/dev/null; sudo rm -rf "$W/data2"
    docker run -d --name s0-dc2 --hostname dc2.ad.lan.test --network s0net --ip 10.88.0.11 --dns "$DC_IP" \
        --cap-drop ALL --cap-add CHOWN --cap-add DAC_OVERRIDE --cap-add FOWNER --cap-add SETUID --cap-add SETGID \
        --security-opt no-new-privileges:true --read-only --tmpfs /run:size=16m --tmpfs /tmp:size=64m \
        --tmpfs /var/log/samba:size=16m --memory 512m \
        -e REALM="$REALM" -e DOMAIN="$DOMAIN" -e HOST_IP=10.88.0.11 -e JOIN_ROLE="$1" -e JOIN_SERVER=dc1.ad.lan.test \
        -v "$W/data2:/data" -v "$W/admin.auth:/run/secrets/join.auth:ro" s0/dc >/dev/null
    for _ in $(seq 1 90); do docker logs s0-dc2 2>&1 | grep -qE "Starting process|^ERROR" && break; sleep 2; done; sleep 10
    docker logs s0-dc2 2>&1 | grep -q "^joined" || { echo "FAIL join as $1"; docker logs s0-dc2 2>&1 | tail -6; return 1; }
}
echo "site DC now: $(kind)"
rejoin RODC && [ "$(kind)" = read-only ] && echo "PASS writable -> read-only (demoted, joined again as dc2)" \
    || echo "FAIL to read-only: $(kind)"
docker exec s0-dc2 ldbsearch -H /data/private/sam.ldb -b "$B" "(sAMAccountName=h2offline)" dn 2>/dev/null | grep -q "^dn:" \
    && echo "PASS the read-only DC has the site's data again (h2offline)" || echo "FAIL data on the read-only DC"
rejoin DC && [ "$(kind)" = writable ] && echo "PASS read-only -> writable (demoted, joined again as dc2)" \
    || echo "FAIL to writable: $(kind)"
[ "$(docker exec s0-dc ldbsearch -H /data/private/sam.ldb -b "$B" "(sAMAccountName=DC2\$)" dn 2>/dev/null | grep -c '^dn:')" = 1 ] \
    && echo "PASS one account for dc2 after both changes (no leftovers)" || echo "FAIL leftover dc2 accounts"
