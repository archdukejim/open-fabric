#!/bin/bash
# RFC2136 dynamic updates the way nginx-proxy-manager's certbot rfc2136
# plugin does them, against the running fabric (inside the sandbox).
#   rfc2136_test.sh <server-ip> <zone> <key-name> <secret> <allowed-host> [<bind-port>]
# Updates and the read-back go to BIND's port (bind_dns_port: 5053 behind the DNS filter): the DNS filter's resolver on 53 caches.
# The secret is written to a 0600 key file; it is never an nsupdate argument.
set -uo pipefail
SERVER=$1 ZONE=$2 KEY=$3 SECRET=$4 HOST=$5 PORT=${6:-53}
PASS=0; FAIL=0
check() { if eval "$2"; then echo "PASS $1"; PASS=$((PASS+1)); else echo "FAIL $1"; FAIL=$((FAIL+1)); fi; }
tmp=$(mktemp -d); trap 'rm -rf "$tmp"' EXIT
keyfile() { umask 077; printf 'key "%s" {\n    algorithm hmac-sha256;\n    secret "%s";\n};\n' "$KEY" "$1" > "$tmp/key"; }
update() {  # secret name value -> nsupdate exit code
    keyfile "$1"
    { printf 'server %s %s\nzone %s\nupdate delete %s TXT\n' "$SERVER" "$PORT" "$ZONE" "$2"
      [ -n "$3" ] && printf 'update add %s 60 TXT "%s"\n' "$2" "$3"
      printf 'send\n'; } > "$tmp/cmds"
    nsupdate -t 10 -k "$tmp/key" "$tmp/cmds" > "$tmp/out" 2>&1
}
token="t$(date +%s)"
update "$SECRET" "_acme-challenge.$HOST.$ZONE." "$token"
check "RFC2136 update with the embedded key accepted" "[ $? = 0 ]"
check "the TXT record is served" "dig +short TXT -p $PORT @$SERVER _acme-challenge.$HOST.$ZONE | grep -q $token"
update "$SECRET" "_acme-challenge.other.$ZONE." "x"
check "name outside the key's grant refused" "[ $? != 0 ] && grep -qi refused '$tmp/out'"
update "$(printf 'wrongwrongwrongwrongwrongwrongwr' | base64)" "_acme-challenge.$HOST.$ZONE." "x"
check "wrong secret refused" "[ $? != 0 ]"
update "$SECRET" "_acme-challenge.$HOST.$ZONE." ""   # clean up like certbot does
echo "$PASS passed, $FAIL failed"
exit $FAIL
