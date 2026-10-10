#!/bin/bash
# Spike (manual 2.3.12.1, Q8): the resolver's memory and load time by lists and client groups (views).
# Each case starts a fresh named with N views, each loading the given lists, and reads its memory once loaded.
#     bash spikes/dns-filter/measure.sh "VIEWS:LIST,LIST" ...    e.g.  measure.sh 1: 1:1 2:1 4:1 1:5 1:48 1:1,48
set -uo pipefail
W=${SPIKE_DIR:-$HOME/fabric-spike-dns}
IMG=fabric-spike/bind9-dnsfilter
THREADS=${THREADS:-4}
C=$W/measure
printf '%-16s %8s %10s %10s\n' "views:lists" records "load" "memory"
for case in "$@"; do
    views=${case%%:*}; lists=${case#*:}
    rm -rf "$C"; mkdir -p "$C/zones" "$C/log"; chmod a+rwX "$C/log"
    records=0; zones=""; policy=""
    for id in ${lists//,/ }; do
        cp "$W/zones/list$id.rpz" "$C/zones/"
        records=$((records + $(grep -c ' CNAME ' "$C/zones/list$id.rpz")))
        zones="$zones zone \"list$id.rpz\" { type primary; file \"/etc/bind/zones/list$id.rpz\"; };"
        policy="$policy zone \"list$id.rpz\";"
    done
    {
        echo 'options { directory "/var/cache/bind"; listen-on-v6 { none; }; recursion yes;'
        echo '  session-keyfile "/var/cache/bind/session.key"; };'
        echo 'logging { channel g { file "/var/log/named/general.log"; }; category default { g; }; };'
        for v in $(seq 1 "$views"); do
            echo "view \"v$v\" { match-clients { $([ "$v" = "$views" ] && echo any || echo "10.$v.0.0/16"); };"
            [ "$v" -gt 1 ] && echo '  attach-cache "v1";'
            [ -n "$zones" ] && echo "  $zones response-policy { $policy } qname-wait-recurse no;"
            echo '};'
        done
    } > "$C/named.conf"
    docker rm -f sdf-measure >/dev/null 2>&1
    start=$(date +%s%N)
    docker run -d --name sdf-measure --memory 2g -v "$C/named.conf:/etc/bind/named.conf:ro" \
        -v "$C/zones:/etc/bind/zones:ro" -v "$C/log:/var/log/named" "$IMG" \
        named -f -n "$THREADS" -u bind -c /etc/bind/named.conf >/dev/null
    for _ in $(seq 1 1200); do grep -qs "running$" "$C/log/general.log" && break; sleep 0.1; done
    load=$(( ($(date +%s%N) - start) / 1000000 ))
    sleep 3
    mem=$(docker stats --no-stream --format '{{.MemUsage}}' sdf-measure | cut -d/ -f1)
    grep -qs "running$" "$C/log/general.log" || { mem="did not start"; tail -3 "$C/log/general.log"; }
    printf '%-16s %8s %8sms %10s\n' "$case" "$((records * views))" "$load" "$mem"
    docker rm -f sdf-measure >/dev/null 2>&1
done
