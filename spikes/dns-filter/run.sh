#!/bin/bash
# Spike for 2.1.12.3 (manual 2.3.12.1, Q8): BIND 9.20 as fabric's filtering resolver, before anything is built.
#   - a second BIND resolves for clients; fabric's zone is forwarded to the authoritative BIND, never filtered
#   - lists from AdGuard's catalogue, converted by convert.py, as response policy zones
#   - client groups as views (match-clients), one cache shared (attach-cache); each view loads its own lists
#   - internet names to Cloudflare over DoT, the certificate's name verified
#   - safe search: CNAME rewrites to each engine's enforced name, for one group only
#   - DoT (853) and DoH (/dns-query) towards clients; a client outside the allowed networks refused
#   - the query log and the RPZ log, as fabric would read them
#   - memory and load time: no lists, the default list, a large set
# Needs: fetch.sh run first (the lists), internet access (Cloudflare). Throwaway (global Rule 4): a self-signed
# certificate made here; nothing is kept but ~/fabric-spike-dns.
#     bash spikes/dns-filter/run.sh [lists...]      list ids from AdGuard's catalogue, default: 1 (AdGuard DNS filter)
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
W=${SPIKE_DIR:-$HOME/fabric-spike-dns}
LISTS=("${@:-1}")
THREADS=${THREADS:-4}    # the test Pi has 4 cores; named starts one worker per CPU
NET=spike_dnsf_net
SUB=172.30.53
IMG=fabric-spike/bind9-dnsfilter
FAILED=0
check() { if [ "$1" = 0 ]; then echo "PASS $2"; else echo "FAIL $2"; FAILED=$((FAILED + 1)); fi; }
cleanup() {
    docker rm -f sdf-auth sdf-resolver sdf-kid sdf-adult sdf-stranger >/dev/null 2>&1
    docker network rm "$NET" >/dev/null 2>&1
}
cleanup
[ -s "$W/zones/list1.rpz" ] || { echo "run fetch.sh first"; exit 1; }

# ---- the image: the same Debian base fabric's BIND is built on, with dig for the clients
BASE=$(python3 "$REPO/tests/image_ref.py" debian) || exit 1
docker build -q -t "$IMG" - >/dev/null <<EOF || exit 1
FROM $BASE
RUN apt-get update && apt-get install -y --no-install-recommends bind9 bind9-utils bind9-dnsutils ca-certificates \
    openssl && rm -rf /var/lib/apt/lists/*
EOF
echo "BIND: $(docker run --rm "$IMG" named -v)"

C=$W/conf; rm -rf "$C"; mkdir -p "$C/auth" "$C/res/zones" "$C/res/log" "$C/res/tls"
# ---- the authoritative BIND: fabric's zone (site.test), as fabric renders it
cat > "$C/auth/named.conf" <<'EOF'
options { directory "/var/cache/bind"; recursion no; allow-query { any; }; listen-on-v6 { none; }; };
zone "site.test" { type primary; file "/etc/bind/site.test.db"; };
EOF
cat > "$C/auth/site.test.db" <<'EOF'
$TTL 300
@ SOA ns.site.test. hostmaster.site.test. 1 3600 600 86400 300
@ NS ns.site.test.
ns A 172.30.53.10
www A 10.1.2.3
ads A 10.1.2.4
EOF

# ---- the resolver's zones: fabric's passthru, the owner's rules, safe search, the lists
cat > "$C/res/zones/fabric.rpz" <<'EOF'
$TTL 300
@ SOA localhost. hostmaster.fabric.rpz. 1 3600 600 86400 300
@ NS localhost.
site.test CNAME rpz-passthru.
*.site.test CNAME rpz-passthru.
EOF
cat > "$C/res/zones/owner.rpz" <<'EOF'
$TTL 300
@ SOA localhost. hostmaster.owner.rpz. 1 3600 600 86400 300
@ NS localhost.
; the owner's own block, and an allow that beats a list
blocked-by-owner.example CNAME .
doubleclick.net CNAME rpz-passthru.
EOF
cat > "$C/res/zones/safesearch.rpz" <<'EOF'
$TTL 300
@ SOA localhost. hostmaster.safesearch.rpz. 1 3600 600 86400 300
@ NS localhost.
www.google.com CNAME forcesafesearch.google.com.
www.bing.com CNAME strict.bing.com.
duckduckgo.com CNAME safe.duckduckgo.com.
www.youtube.com CNAME restrictmoderate.youtube.com.
EOF
# a list holding a fabric name, to prove fabric's zone is never filtered
printf '%s\n' '$TTL 300' '@ SOA localhost. hostmaster.test.rpz. 1 3600 600 86400 300' '@ NS localhost.' \
    'ads.site.test CNAME .' > "$C/res/zones/testlist.rpz"
POLICY=""; LISTZONES=""
for id in "${LISTS[@]}"; do
    cp "$W/zones/list$id.rpz" "$C/res/zones/"
    POLICY="$POLICY zone \"list$id.rpz\";"
    LISTZONES="$LISTZONES zone \"list$id.rpz\" { type primary; file \"/etc/bind/zones/list$id.rpz\"; };"$'\n'
done
VIEWZONES="    zone \"site.test\" { type forward; forward only; forwarders { $SUB.10; }; };
    zone \"fabric.rpz\" { type primary; file \"/etc/bind/zones/fabric.rpz\"; };
    zone \"owner.rpz\" { type primary; file \"/etc/bind/zones/owner.rpz\"; };
    zone \"testlist.rpz\" { type primary; file \"/etc/bind/zones/testlist.rpz\"; };
$LISTZONES"
# finding: RPZ zones and forward zones cannot be shared with in-view, so a group view either loads its own copy of
# every list (MODE=copy) or keeps only its own policy and forwards the rest to the main view (MODE=chain)
MODE=${MODE:-copy}
if [ "$MODE" = chain ]; then
    KIDSVIEW="view \"kids\" {
    match-clients { $SUB.101; };
    forward only; forwarders { 127.0.0.1; };
    // finding: validating here breaks (DS lookups for a listed name are blocked by the main view); the main view
    // validates what it answers, the upstream what the group's allows send it
    dnssec-validation no;
    zone \"safesearch.rpz\" { type primary; file \"/etc/bind/zones/safesearch.rpz\"; };
    // the group's own allow: resolved past the main view's lists, straight to the upstream
    zone \"doubleclick.com\" { type forward; forward only; forwarders port 853 tls cloudflare { 1.1.1.1; 1.0.0.1; }; };
    response-policy { zone \"safesearch.rpz\"; } break-dnssec yes qname-wait-recurse no;
};"
else
    KIDSVIEW="view \"kids\" {
    match-clients { $SUB.101; };
$VIEWZONES
    zone \"safesearch.rpz\" { type primary; file \"/etc/bind/zones/safesearch.rpz\"; };
    response-policy { zone \"fabric.rpz\"; zone \"owner.rpz\"; zone \"safesearch.rpz\"; zone \"testlist.rpz\";$POLICY }
        break-dnssec yes qname-wait-recurse no;
};"
fi
openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -days 2 -subj "/CN=dns.site.test" \
    -addext "subjectAltName=DNS:dns.site.test" -keyout "$C/res/tls/key.pem" -out "$C/res/tls/cert.pem" 2>/dev/null
cat > "$C/res/named.conf" <<EOF
tls cloudflare { remote-hostname "cloudflare-dns.com"; ca-file "/etc/ssl/certs/ca-certificates.crt"; };
tls local { cert-file "/etc/bind/tls/cert.pem"; key-file "/etc/bind/tls/key.pem"; };
http doh { endpoints { "/dns-query"; }; };
acl clients { $SUB.0/25; 127.0.0.1; };
options {
    directory "/var/cache/bind";
    listen-on { any; }; listen-on-v6 { none; };
    listen-on port 853 tls local { any; };
    listen-on port 443 tls local http doh { any; };
    recursion yes;
    allow-query { clients; }; allow-recursion { clients; }; allow-query-cache { clients; };
    forwarders port 853 tls cloudflare { 1.1.1.1; 1.0.0.1; };
    forward only;
    dnssec-validation auto;
    validate-except { "site.test"; };
    querylog yes;
    session-keyfile "/var/cache/bind/session.key";
};
logging {
    channel queries { file "/var/log/named/query.log" versions 2 size 20m; print-time yes; };
    channel rpz { file "/var/log/named/rpz.log" versions 2 size 20m; print-time yes; };
    category queries { queries; };
    category rpz { rpz; };
    channel general { file "/var/log/named/general.log"; print-time yes; };
    category default { general; };
};
$KIDSVIEW
view "everyone" {
    match-clients { any; };
$VIEWZONES
    response-policy { zone "fabric.rpz"; zone "owner.rpz"; zone "testlist.rpz";$POLICY }
        break-dnssec yes qname-wait-recurse no;
};
EOF

docker network create --subnet "$SUB.0/24" "$NET" >/dev/null || exit 1
docker run -d --name sdf-auth --network "$NET" --ip "$SUB.10" -v "$C/auth:/etc/bind:ro" "$IMG" \
    named -g -u bind -c /etc/bind/named.conf >/dev/null
chmod -R a+rwX "$C/res/log"
chmod a+r "$C/res/tls/key.pem"    # a throwaway key, read by named as bind
START=$(date +%s%N)
docker run -d --name sdf-resolver --network "$NET" --ip "$SUB.20" --memory 1g \
    -v "$C/res/named.conf:/etc/bind/named.conf:ro" -v "$C/res/zones:/etc/bind/zones:ro" \
    -v "$C/res/tls:/etc/bind/tls:ro" -v "$C/res/log:/var/log/named" "$IMG" \
    named -f -n "$THREADS" -u bind -c /etc/bind/named.conf >/dev/null
for _ in $(seq 1 600); do
    grep -qs "running$" "$C/res/log/general.log" && break
    docker inspect -f '{{.State.Running}}' sdf-resolver 2>/dev/null | grep -q true || break
    sleep 0.2
done
LOADED=$(( ($(date +%s%N) - START) / 1000000 ))ms
if ! grep -qs "running$" "$C/res/log/general.log"; then
    echo "the resolver did not start:"; docker logs sdf-resolver 2>&1 | tail -30; tail -30 "$C/res/log/general.log"; cleanup; exit 1
fi
echo "resolver up in ${LOADED} with lists: ${LISTS[*]} (${THREADS} threads, 2 views)"
sleep 2
echo "memory, lists loaded: $(docker stats --no-stream --format '{{.MemUsage}}' sdf-resolver)"

for c in kid:101 adult:102 stranger:200; do
    docker run -d --name "sdf-${c%%:*}" --network "$NET" --ip "$SUB.${c##*:}" "$IMG" sleep 600 >/dev/null
done
q() { docker exec "sdf-$1" dig +time=5 +tries=1 "${@:2}" @"$SUB.20"; }
short() { q "$@" +short | tr '\n' ' '; }

# ---- fabric's zone: resolved through the authoritative BIND, never filtered (even when a list names it)
[ "$(short adult www.site.test)" = "10.1.2.3 " ]; check $? "fabric's zone answers through the authoritative BIND"
[ "$(short adult ads.site.test)" = "10.1.2.4 " ]; check $? "a list naming a fabric name does not block it (passthru first)"
# ---- internet over DoT, and DNSSEC still validated
q adult example.com | grep -q "status: NOERROR"; check $? "an internet name resolves (Cloudflare over DoT)"
q adult example.com +dnssec | grep -q " ad;"; check $? "DNSSEC validated (ad flag) through the DoT forwarder"
# ---- the lists
q adult doubleclick.com | grep -q "status: NXDOMAIN"; check $? "a listed name answers NXDOMAIN (AdGuard DNS filter)"
q adult sub.doubleclick.com | grep -q "status: NXDOMAIN"; check $? "a name below a ||name^ rule is blocked too"
q adult doubleclick.net | grep -q "status: NOERROR"; check $? "the owner's allow beats a list"
q adult blocked-by-owner.example | grep -q "status: NXDOMAIN"; check $? "the owner's block"
# ---- groups: the kid has safe search, the adult does not; both share the lists
[[ "$(short kid www.google.com)" == forcesafesearch.google.com.* ]]; check $? "kid: Google rewritten to forcesafesearch"
[[ "$(short kid www.bing.com)" == strict.bing.com.* ]]; check $? "kid: Bing strict"
[[ "$(short kid duckduckgo.com)" == safe.duckduckgo.com.* ]]; check $? "kid: DuckDuckGo safe"
[[ "$(short kid www.youtube.com)" == restrictmoderate.youtube.com.* ]]; check $? "kid: YouTube moderate"
[[ "$(short adult www.google.com)" != forcesafesearch* ]]; check $? "adult: Google not rewritten"
q kid adnxs.com | grep -q "status: NXDOMAIN"; check $? "kid: the list applies to the group too"
[ "$(short kid www.site.test)" = "10.1.2.3 " ]; check $? "kid: fabric's zone answers"
[ "$(short kid ads.site.test)" = "10.1.2.4 " ]; check $? "kid: fabric's zone never filtered"
if [ "$MODE" = chain ]; then
    q kid doubleclick.com | grep -q "status: NOERROR"; check $? "kid: the group's own allow beats the main view's list"
    q adult doubleclick.com | grep -q "status: NXDOMAIN"; check $? "adult: the same name still blocked"
    [ "$(short kid www.google.com | wc -w)" -ge 2 ]; check $? "kid: the safe-search target resolved through the main view"
fi
# ---- refused outside the allowed networks
q stranger example.com | grep -q "status: REFUSED"; check $? "a client outside the allowed networks is refused"
# ---- DoT and DoH towards clients
docker cp "$C/res/tls/cert.pem" sdf-adult:/tmp/ca.pem
docker exec sdf-adult dig +tls +tls-ca=/tmp/ca.pem +tls-hostname=dns.site.test @"$SUB.20" www.site.test +short \
    | grep -q 10.1.2.3; check $? "DoT (853) towards clients, the certificate verified"
docker exec sdf-adult dig +https +tls-ca=/tmp/ca.pem +tls-hostname=dns.site.test @"$SUB.20" doubleclick.com \
    | grep -q "status: NXDOMAIN"; check $? "DoH (/dns-query) towards clients, filtered"
# ---- the logs fabric would read
sleep 1
echo "query log sample:"; tail -n 3 "$C/res/log/query.log" | sed 's/^/    /'
echo "rpz log sample:";   tail -n 3 "$C/res/log/rpz.log" | sed 's/^/    /'
grep -q "doubleclick.com" "$C/res/log/rpz.log"; check $? "the RPZ log names the blocked name and its zone"
echo "memory, after the tests: $(docker stats --no-stream --format '{{.MemUsage}}' sdf-resolver)"
echo "FAILED: $FAILED"
[ -n "${KEEP:-}" ] || cleanup
exit "$FAILED"
