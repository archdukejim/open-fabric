#!/bin/bash
# S0 spike (manual 2.3.6.1.5): shared setup. Throwaway: never merged into src/.
# Everything is named s0-* (containers, network s0net, images s0/*) and lives in $W; nothing else is touched.
set -u
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
W=${S0_WORK:-/var/tmp/s0}
REALM=AD.LAN.TEST; DOMAIN=LAN; DC_IP=10.88.0.10; B="DC=ad,DC=lan,DC=test"
mkdir -p "$W/secrets"

# Purpose: a random password that meets AD's complexity rules, written to a 0600 file (never on argv).
# Inputs:  $1 — file path. Returns: nothing; the file holds the password. Fails: never.
# Feeds:   the q*.sh scripts.
new_password() {
    (umask 077; { head -c 15 /dev/urandom | base64 | tr -d '/+=\n'; printf 'Aa1!'; } > "$1")
}

# Purpose: a Samba credentials file (-A) for a user and its password file.
# Inputs:  $1 — user; $2 — password file; $3 — output file. Returns: nothing. Fails: never.
# Feeds:   the q*.sh scripts (smbclient, ldbsearch, ldbadd as that user).
auth_file() {
    (umask 077; printf 'username=%s\npassword=%s\ndomain=%s\n' "$1" "$(cat "$2")" "$DOMAIN" > "$3")
}

# Purpose: start the DC (provisioning a fresh domain when $W/data is empty), hardened as fabric would run it.
# Inputs:  CAPS (env) — capabilities to keep (default: what provisioning needs); SAMBA_DEBUG (env, optional).
# Returns: when samba has started (or after 120 s). Fails: never; the q*.sh checks say what broke.
# Feeds:   q1.sh, q2.sh.
start_dc() {
    local caps=${CAPS:-CHOWN DAC_OVERRIDE FOWNER SETUID SETGID} add=() c
    for c in $caps; do add+=(--cap-add "$c"); done
    docker network inspect s0net >/dev/null 2>&1 || docker network create --subnet 10.88.0.0/24 s0net >/dev/null
    [ -s "$W/secrets/admin_password" ] || new_password "$W/secrets/admin_password"
    docker rm -f s0-dc >/dev/null 2>&1
    docker run -d --name s0-dc --hostname dc1.ad.lan.test --network s0net --ip "$DC_IP" --dns "$DC_IP" \
        --cap-drop ALL "${add[@]}" --security-opt no-new-privileges:true --read-only \
        --tmpfs /run:size=16m --tmpfs /tmp:size=64m --tmpfs /var/log/samba:size=16m --memory 512m \
        -v "$W/winbindd:/run/samba/winbindd" \
        -e REALM="$REALM" -e DOMAIN="$DOMAIN" -e HOST_IP="$DC_IP" ${SAMBA_DEBUG:+-e SAMBA_DEBUG=$SAMBA_DEBUG} \
        -v "$W/data:/data" -v "$W/secrets/admin_password:/run/secrets/admin_password:ro" s0/dc >/dev/null
    for _ in $(seq 1 60); do docker logs s0-dc 2>&1 | grep -q "Starting process" && break; sleep 2; done
    sleep 10
}

# Purpose: start BIND (fabric's image plus Samba's DLZ module) in the DC's network namespace — the two share one
#          address, as they would share the host's — hardened as fabric runs BIND (uid 600, no capabilities).
# Inputs:  none. Returns: after BIND has had 8 s to load. Fails: never.
# Feeds:   q2.sh.
start_bind() {
    docker rm -f s0-bind >/dev/null 2>&1
    docker run -d --name s0-bind --network container:s0-dc --cap-drop ALL --security-opt no-new-privileges:true \
        --read-only --tmpfs /tmp:size=16m --tmpfs /var/tmp:size=16m,uid=600,gid=600 \
        --tmpfs /run/named:size=8m,uid=600,gid=600 --tmpfs /var/cache/bind:size=16m,uid=600,gid=600 --memory 128m \
        -v "$W/data/bind-dns:/data/bind-dns" -v "$W/data/etc/smb.conf:/etc/samba/smb.conf:ro" s0/bind >/dev/null
    sleep 8
}

# Purpose: run a command in a throwaway client container on the spike network (the DC image has the tools).
# Inputs:  $@ — docker run options, then `--`, then the command. Returns: the command's status. Fails: never.
# Feeds:   the q*.sh scripts.
client() {
    local opts=()
    while [ "$1" != "--" ]; do opts+=("$1"); shift; done; shift
    docker run --rm --network s0net --dns "$DC_IP" "${opts[@]}" --entrypoint "$1" s0/dc "${@:2}"
}

build_images() {
    docker build -q -t s0/dc "$HERE/dc" >/dev/null && docker build -q -t s0/bind "$HERE/bind" >/dev/null
}

# Purpose: remove everything the spike made. Inputs: none. Returns: nothing. Fails: never.
# Feeds:   clean.sh.
clean_all() {
    docker rm -f s0-dc s0-bind >/dev/null 2>&1
    docker network rm s0net >/dev/null 2>&1
    sudo rm -rf "$W"
}
