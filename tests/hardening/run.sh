#!/bin/bash
# -----------------------------------------------------------------------
# Hardening suite: start bind9, step-ca, postgres, keycloak and dirsrv from
# the REAL rendered compose files (docker compose up, including the local
# build layers), prove each one works, and assert from the host that it is
# hardened: non-root, all capabilities dropped and none added,
# no-new-privileges, read-only root filesystem, zero effective capabilities.
#
# Uses the 4 GB memory limits (host_ram_capacity=4) so limits are exercised.
# Needs root, Docker with compose v2, python3 (yaml, jinja2), openssl, curl.
# Creates and removes the docker network fabric_net — do not run on a host
# that runs a live fabric stack.
# -----------------------------------------------------------------------
set -uo pipefail
exec 9>/tmp/fabric-hardening-suite.lock
flock -n 9 || { echo "another hardening run is active; refusing to start" >&2; exit 2; }
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
OUT="${FABRIC_TEST_OUT:-/tmp/fabric-tests}"
W="$OUT/hardening"
BASE="$W/opt"
DOMAIN=lan.j-j.family
PASS=0; FAIL=0
check() { if eval "$2"; then echo "PASS $1"; PASS=$((PASS+1)); else echo "FAIL $1"; FAIL=$((FAIL+1)); fi; }

down_all() {
    for s in dirsrv keycloak postgres stepca bind9; do
        [ -f "$W/rendered/$s/docker-compose.yml" ] && docker compose -f "$W/rendered/$s/docker-compose.yml" down -v >/dev/null 2>&1
    done
    docker network rm fabric_net >/dev/null 2>&1
}
if docker network inspect fabric_net >/dev/null 2>&1 && docker ps --format '{{.Names}}' | grep -qx nginx; then
    echo "A fabric stack seems to be running here (nginx on fabric_net); refusing." >&2; exit 2
fi
down_all
rm -rf "$W"; mkdir -p "$BASE"

# ---- render with test-safe values ------------------------------------
export FABRIC_TEST_VARS="{\"deploy_base_dir\": \"$BASE\", \"host_ip\": \"127.0.0.1\", \"bind_dns_port\": 10053,
  \"host_ram_capacity\": 4, \"hostname\": \"pi-core\", \"stepca_port\": 9000}"
python3 "$REPO/tests/render.py" "$W/rendered" >/dev/null || { echo "FAIL render"; exit 1; }
R="$W/rendered"
docker network create --subnet 10.255.0.0/24 fabric_net >/dev/null
# Build contexts go where deploy.py puts them (/opt/<svc>/build)
for s in bind9 stepca keycloak dirsrv; do mkdir -p "$BASE/$s"; cp -a "$REPO/fabric/jinja/$s/build" "$BASE/$s/build"; done

# ---- PKI: root -> intermediate -> leaves -----------------------------
cd "$W"
openssl req -x509 -newkey rsa:2048 -nodes -keyout root.key -out root.crt -days 2 -subj '/CN=Test Root' \
  -addext basicConstraints=critical,CA:TRUE -addext keyUsage=critical,keyCertSign,cRLSign 2>/dev/null
openssl req -newkey rsa:2048 -nodes -keyout int.key -out int.csr -subj '/CN=Test Int' 2>/dev/null
printf 'basicConstraints=critical,CA:TRUE,pathlen:0\nkeyUsage=critical,keyCertSign,cRLSign\n' > int.ext
openssl x509 -req -in int.csr -CA root.crt -CAkey root.key -CAcreateserial -out int.crt -days 2 -extfile int.ext 2>/dev/null
leaf() {  # name san...
    local n="$1"; shift
    local sans; sans=$(printf 'DNS:%s,' "$@"); sans=${sans%,}
    openssl req -newkey rsa:2048 -nodes -keyout "$n.key" -out "$n.csr" -subj "/CN=$1" 2>/dev/null
    printf 'subjectAltName=%s\nextendedKeyUsage=serverAuth,clientAuth\n' "$sans" > "$n.ext"
    openssl x509 -req -in "$n.csr" -CA int.crt -CAkey int.key -CAcreateserial -out "$n.crt" -days 2 -extfile "$n.ext" 2>/dev/null
    cat "$n.crt" int.crt > "$n.chain"
}
leaf dns "dns.$DOMAIN" "ns.$DOMAIN"
leaf pg postgres "postgres.$DOMAIN"
leaf kc "sso.$DOMAIN"
leaf ldap "ldap.$DOMAIN"

# ---- assertions ----------------------------------------------------------
hardened() {  # container, expect_readonly(1/0)
    python3 - "$1" "${2:-1}" <<'PY'
import json, subprocess, sys
name, want_ro = sys.argv[1], sys.argv[2] == "1"
found = json.loads(subprocess.run(["docker", "inspect", name], capture_output=True, text=True).stdout or "[]")
if not found:
    print("container not running"); sys.exit(1)
info = found[0]
hc, cfg = info["HostConfig"], info["Config"]
user = (cfg.get("User") or "root").split(":")[0]
pid = info["State"]["Pid"]
if not pid:
    print(f"container not running ({info['State']['Status']})"); sys.exit(1)
capeff = next(l.split()[1] for l in open(f"/proc/{pid}/status") if l.startswith("CapEff"))
problems = []
if user in ("", "0", "root"): problems.append(f"runs as root ({user!r})")
if (hc.get("CapDrop") or []) != ["ALL"]: problems.append(f"CapDrop={hc.get('CapDrop')}")
if hc.get("CapAdd"): problems.append(f"CapAdd={hc.get('CapAdd')}")
if "no-new-privileges:true" not in (hc.get("SecurityOpt") or []): problems.append("no-new-privileges missing")
if want_ro and not hc.get("ReadonlyRootfs"): problems.append("root filesystem writable")
if int(capeff, 16) != 0: problems.append(f"effective capabilities {capeff}")
if not hc.get("Memory"): problems.append("no memory limit")
print("; ".join(problems) if problems else f"ok (user {user}, CapEff {capeff}, mem {hc['Memory']//2**20}M)")
sys.exit(1 if problems else 0)
PY
}
wait_healthy() {  # container, timeout
    local t=0
    while [ "$t" -lt "${2:-240}" ]; do
        case "$(docker inspect -f '{{.State.Health.Status}}' "$1" 2>/dev/null)" in
            healthy) return 0 ;;
            unhealthy) docker logs --tail 30 "$1"; return 1 ;;
        esac
        docker ps -q -f name="^$1$" | grep -q . || { docker logs --tail 30 "$1" 2>&1; return 1; }
        sleep 3; t=$((t+3))
    done
    docker logs --tail 30 "$1"; return 1
}
up() { docker compose -f "$R/$1/docker-compose.yml" up -d --build >"$W/$1-up.log" 2>&1 || { tail -20 "$W/$1-up.log"; return 1; }; }

# ---- bind9 -------------------------------------------------------------
echo "--- bind9"
mkdir -p "$BASE/bind9"/{config,data,log,cache,ssl}
cp "$R"/bind9/config/* "$BASE/bind9/config/"
for z in $(grep -o 'db\.[^"]*' "$R/bind9/config/named.conf.zones"); do
    if [ "$z" = "db.$DOMAIN" ]; then cp "$R/bind9/data/zone" "$BASE/bind9/data/$z"
    else printf '$TTL 3600\n@ IN SOA ns.%s. hostmaster.%s. (1 3600 900 604800 300)\n@ IN NS ns.%s.\n' "$DOMAIN" "$DOMAIN" "$DOMAIN" > "$BASE/bind9/data/$z"; fi
done
cp dns.chain "$BASE/bind9/ssl/fullchain.pem"; cp dns.key "$BASE/bind9/ssl/privkey.pem"; cp root.crt "$BASE/bind9/ssl/root_ca.crt"
chown -R 53:53 "$BASE/bind9"; chmod 600 "$BASE/bind9/config/rndc.key" "$BASE/bind9/config/named.conf.keys" "$BASE/bind9/ssl/privkey.pem"
check "bind9 builds and becomes healthy" "up bind9 && wait_healthy bind9"
check "bind9 hardened: $(hardened bind9 1 | tr -d '\n')" "hardened bind9 1 >/dev/null"
dnsq() {  # name server port -> first A answer (tiny stdlib DNS client)
    python3 - "$@" <<'PY'
import random, socket, struct, sys
name, server, port = sys.argv[1], sys.argv[2], int(sys.argv[3])
qid = random.randint(0, 65535)
q = struct.pack(">HHHHHH", qid, 0x0100, 1, 0, 0, 0) + b"".join(
    bytes([len(p)]) + p.encode() for p in name.rstrip(".").split(".")) + b"\0" + struct.pack(">HH", 1, 1)
s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.settimeout(3); s.sendto(q, (server, port))
data = s.recv(512); an = struct.unpack(">H", data[6:8])[0]
i = 12 + len(q) - 12
for _ in range(an):
    while data[i] and data[i] < 0xc0: i += data[i] + 1
    i += 2 if data[i] >= 0xc0 else 1
    rtype, _, _, rdlen = struct.unpack(">HHIH", data[i:i + 10]); i += 10
    if rtype == 1: print(".".join(map(str, data[i:i + 4]))); break
    i += rdlen
PY
}
check "bind9 answers (pi-core.$DOMAIN via published port)" "[ \"\$(dnsq pi-core.$DOMAIN 127.0.0.1 10053)\" = 127.0.0.1 ]"
check "bind9 follows CNAME (ca.$DOMAIN -> pi-core)" "[ \"\$(dnsq ca.$DOMAIN 127.0.0.1 10053)\" = 127.0.0.1 ]"

# ---- step-ca -------------------------------------------------------------
echo "--- step-ca"
mkdir -p "$BASE/stepca/data/secrets"; openssl rand -hex 16 > "$BASE/stepca/data/secrets/password"
chown -R 135:135 "$BASE/stepca"
docker run --rm --user 135:135 -v "$BASE/stepca/data:/home/step" -e STEPPATH=/home/step \
  "$(python3 -c "import yaml;print(yaml.safe_load(open('$R/vars.yaml'))['image_stepca'])")" \
  step ca init --name "Test CA" --dns "ca.$DOMAIN" --dns 127.0.0.1 --address :9000 --provisioner admin \
  --password-file /home/step/secrets/password --provisioner-password-file /home/step/secrets/password \
  >"$W/stepca-init.log" 2>&1
check "step-ca becomes healthy (step ca health over DNS from bind9)" "up stepca && wait_healthy step-ca"
check "step-ca hardened: $(hardened step-ca 1 | tr -d '\n')" "hardened step-ca 1 >/dev/null"

# ---- postgres ---------------------------------------------------------------
echo "--- postgres"
mkdir -p "$BASE/postgres/data" "$BASE/postgres/certs"
cp pg.chain "$BASE/postgres/certs/fullchain.pem"; cp pg.key "$BASE/postgres/certs/privkey.pem"
chown -R 901:901 "$BASE/postgres"; chmod 600 "$BASE/postgres/certs/privkey.pem"
check "postgres initialises and becomes healthy" "up postgres && wait_healthy postgres"
check "postgres hardened: $(hardened postgres 1 | tr -d '\n')" "hardened postgres 1 >/dev/null"
check "postgres serves TLS" "docker exec postgres psql -U keycloak -d keycloak -tAc 'show ssl' | grep -qx on"

# ---- keycloak ---------------------------------------------------------------
echo "--- keycloak"
mkdir -p "$BASE/keycloak/data" "$BASE/keycloak/certs"
cp kc.chain "$BASE/keycloak/certs/fullchain.pem"; cp kc.key "$BASE/keycloak/certs/privkey.pem"; cp root.crt "$BASE/keycloak/certs/root_ca.crt"
chown -R 900:0 "$BASE/keycloak"; chmod 600 "$BASE/keycloak/certs/privkey.pem"
check "keycloak (optimized build) starts against postgres (verify-full TLS)" "up keycloak && wait_healthy keycloak 420"
check "keycloak hardened: $(hardened keycloak 1 | tr -d '\n')" "hardened keycloak 1 >/dev/null"
# Health (port 9000) comes up a few seconds before first-boot realm setup ends.
kc_https() { for _ in $(seq 1 30); do curl -sf --cacert root.crt --resolve "sso.$DOMAIN:8443:10.255.0.60" "https://sso.$DOMAIN:8443/realms/master" >/dev/null && return 0; sleep 2; done; return 1; }
check "keycloak serves HTTPS with its cert" "kc_https"
check "keycloak started optimized (no re-augmentation)" "! docker logs keycloak 2>&1 | grep -qi 'Updating the configuration and installing your custom providers'"

# ---- dirsrv -------------------------------------------------------------------
echo "--- dirsrv"
mkdir -p "$BASE/dirsrv/data/tls/ca" "$BASE/dirsrv/seed"
cp ldap.crt "$BASE/dirsrv/data/tls/server.crt"; cp ldap.key "$BASE/dirsrv/data/tls/server.key"
cp root.crt int.crt "$BASE/dirsrv/data/tls/ca/"
cp "$R"/dirsrv/seed/*.ldif "$BASE/dirsrv/seed/"; cp "$REPO/fabric/jinja/dirsrv/seed.py" "$BASE/dirsrv/seed/"
chown -R 911:911 "$BASE/dirsrv/data"; chown -R 0:911 "$BASE/dirsrv/seed"; chmod 750 "$BASE/dirsrv/seed"; chmod 640 "$BASE/dirsrv/seed"/*
check "dirsrv builds and becomes healthy" "up dirsrv && wait_healthy dirsrv"
check "dirsrv hardened: $(hardened dirsrv 1 | tr -d '\n')" "hardened dirsrv 1 >/dev/null"
seed() {
    docker exec dirsrv sh -c 'dsconf localhost backend suffix list 2>/dev/null | grep -qiF "$DS_SUFFIX_NAME (" || dsconf localhost backend create --suffix "$DS_SUFFIX_NAME" --be-name userroot' >/dev/null &&
    docker exec dirsrv sh -c 'python3 /seed/seed.py /seed/*.ldif'
}
check "dirsrv seeds on a read-only root" "seed | tee '$W/seed.log' | grep -q 'seed: '"

echo; echo "$PASS passed, $FAIL failed"
[ "${KEEP:-0}" = 1 ] || { down_all; docker rmi fabric/bind9:local fabric/stepca:local fabric/keycloak:local fabric/dirsrv:local >/dev/null 2>&1; }
exit $FAIL
