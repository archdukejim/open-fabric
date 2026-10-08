#!/bin/bash
# S0 spike Q14: same-domain mode (2.1.6.11) — AD's domain equals fabric's (lan.test). fabric's records then live in AD's
# zone; ACME DNS-01 with TSIG keys is tried straight into that zone and through a CNAME into a zone of BIND's own.
# A separate domain and containers (s0-dcx, s0-bindx); needs only the images.   sudo bash spikes/samba/q14.sh
. "$(dirname "$0")/common.sh"
X=$W/same; XIP=10.88.0.20
echo "--- Q14"
docker rm -f s0-dcx s0-bindx >/dev/null 2>&1; sudo rm -rf "$X"; mkdir -p "$X"
new_password "$X/admin_password"
docker network inspect s0net >/dev/null 2>&1 || docker network create --subnet 10.88.0.0/24 s0net >/dev/null
docker run -d --name s0-dcx --hostname dc1.lan.test --network s0net --ip "$XIP" --dns "$XIP" \
    --cap-drop ALL --cap-add CHOWN --cap-add DAC_OVERRIDE --cap-add FOWNER --cap-add SETUID --cap-add SETGID \
    --security-opt no-new-privileges:true --read-only --tmpfs /run:size=16m --tmpfs /tmp:size=64m \
    --tmpfs /var/log/samba:size=16m --memory 512m -e REALM=LAN.TEST -e DOMAIN=LANX -e HOST_IP="$XIP" \
    -v "$X/data:/data" -v "$X/admin_password:/run/secrets/admin_password:ro" s0/dc >/dev/null
for _ in $(seq 1 60); do docker logs s0-dcx 2>&1 | grep -q "Starting process" && break; sleep 2; done; sleep 10
# the ACME key, readable by BIND (uid 600) only
docker run --rm --entrypoint tsig-keygen s0/bind -a hmac-sha256 acme > "$X/acme.key"
sudo chown 600:600 "$X/acme.key"; sudo chmod 400 "$X/acme.key"
docker run -d --name s0-bindx --network container:s0-dcx --cap-drop ALL --security-opt no-new-privileges:true \
    --read-only --tmpfs /tmp:size=16m --tmpfs /var/tmp:size=16m,uid=600,gid=600 --tmpfs /run/named:size=8m,uid=600,gid=600 \
    --tmpfs /var/cache/bind:size=16m,uid=600,gid=600 --memory 128m \
    -v "$X/data/bind-dns:/data/bind-dns" -v "$X/data/etc/smb.conf:/etc/samba/smb.conf:ro" \
    -v "$HERE/bind-same/named.conf:/etc/bind/named.conf:ro" -v "$HERE/bind-same/db.acme:/etc/bind/db.acme:ro" \
    -v "$X/acme.key:/run/secrets/acme.key:ro" \
    --entrypoint sh s0/bind -c 'cp /etc/bind/db.acme /var/cache/bind/ && exec /usr/local/bin/dlz.sh' >/dev/null
sleep 8
docker logs s0-bindx 2>&1 | grep -q "configured writeable zone 'lan.test'" \
    && echo "PASS BIND serves fabric's own domain from AD's database (DLZ owns lan.test)" \
    || { echo "FAIL BIND"; docker logs s0-bindx 2>&1 | grep -iE "error|fail" | tail -5; }
dig1() { docker run --rm --network s0net --entrypoint dig s0/dc +short @"$XIP" "$@"; }
# fabric's records go into AD's zone (as fabric's deploy would, on the DC as root)
for rec in "www A 10.88.0.80" "ns A $XIP" "_acme-challenge.www CNAME www.acme.lan.test."; do
    set -- $rec
    docker exec s0-dcx samba-tool dns add 127.0.0.1 lan.test "$1" "$2" "$3" -s /data/etc/smb.conf -P >/dev/null 2>&1
done
[ "$(dig1 www.lan.test)" = 10.88.0.80 ] && echo "PASS fabric's records live in AD's zone (www.lan.test)" \
    || echo "FAIL fabric's record: $(dig1 www.lan.test)"
upd() {  # nsupdate commands -> nsupdate's output
    printf "server %s\n%s\nsend\n" "$XIP" "$1" > "$X/upd"
    docker run --rm --network s0net -v "$X/upd:/upd:ro" -v "$X/acme.key:/k:ro" --user 0 --entrypoint nsupdate s0/dc \
        -k /k /upd 2>&1
}
r=$(upd "zone lan.test
update add _acme-challenge.web.lan.test 60 TXT direct")
echo "$r" | grep -qiE "refused|notauth|notzone" \
    && echo "PASS a TSIG update straight into AD's zone is refused: $(echo "$r" | grep -oiE 'REFUSED|NOTAUTH|NOTZONE' | head -1)" \
    || echo "NOTE a TSIG update into AD's zone was accepted: $r"
r=$(upd "zone acme.lan.test
update add www.acme.lan.test 60 TXT token-123")
[ -z "$r" ] && echo "PASS a TSIG update into BIND's own ACME zone is accepted" || echo "FAIL ACME zone update: $r"
# an authoritative-only server hands out the CNAME and the resolver follows it (fabric's BIND recurses for its LAN):
# both links of the chain an ACME validator follows
[ "$(dig1 CNAME _acme-challenge.www.lan.test)" = www.acme.lan.test. ] && dig1 TXT www.acme.lan.test | grep -q token-123 \
    && echo "PASS ACME DNS-01 works through the CNAME (_acme-challenge.www.lan.test -> www.acme.lan.test: the token)" \
    || echo "FAIL the CNAME chain: $(dig1 CNAME _acme-challenge.www.lan.test) / $(dig1 TXT www.acme.lan.test)"
docker rm -f s0-dcx s0-bindx >/dev/null 2>&1
