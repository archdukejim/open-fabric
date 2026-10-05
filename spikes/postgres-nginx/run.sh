#!/bin/bash
# Spike for D104 (manual 1.8.8.16, S8.6): can a site's Postgres replicate to another's with Postgres never on the host?
#   - nginx's stream proxy terminates TLS, requires a client certificate from the organisation's CA and checks its name
#   - Postgres 17+ direct TLS (sslnegotiation=direct, ALPN "postgresql") through it
#   - the hop from nginx to Postgres: TLS (D51) if nginx's stream proxy can speak Postgres's direct TLS; else a Unix
#     socket the two share (no network at all); else plain on the private network
#   - logical replication of one table with a row filter (one writer per row) across that path
#   - refused: no client certificate, another CA's certificate, a valid certificate of a site not linked
# Throwaway (global Rule 4): a test CA and passwords made here, in a 0700 work folder; nothing is kept.
#     sudo bash spikes/postgres-nginx/run.sh [inner]      inner: socket|tls|plain (default socket)
set -uo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
REPO=$(cd "$HERE/../.." && pwd)
INNER=${1:-socket}
W=/tmp/fabric-spike-pg
NET=spike_pg_net
PG=$(python3 "$REPO/tests/image_ref.py" postgres)
NGINX=$(python3 "$REPO/tests/image_ref.py" nginx)
FAILED=0
# status first: an argument's $(...) would reset $?
check() { if [ "$1" = 0 ]; then echo "PASS $2"; else echo "FAIL $2"; FAILED=$((FAILED + 1)); fi; }
cleanup() {
    docker rm -f spg-a spg-b spg-nginx >/dev/null 2>&1
    docker network rm "$NET" >/dev/null 2>&1
    docker volume rm spg_sock >/dev/null 2>&1
}

cleanup
rm -rf "$W" && mkdir -p "$W/certs" && chmod 0700 "$W"
cd "$W/certs" || exit 1
# ---- a test CA (the organisation's root), and another CA a stranger has
mkca() {
    openssl req -x509 -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -keyout "$1.key" -out "$1.crt" -days 2 \
        -subj "/CN=$1" >/dev/null 2>&1
}
mkcert() {    # name, CA, subject alt name (or "")
    openssl req -newkey ec -pkeyopt ec_paramgen_curve:P-256 -nodes -keyout "$1.key" -out "$1.csr" -subj "/CN=$1" \
        >/dev/null 2>&1
    printf '%s\n' "${3:+subjectAltName=$3}" > "$1.ext"
    openssl x509 -req -in "$1.csr" -CA "$2.crt" -CAkey "$2.key" -CAcreateserial -days 2 -out "$1.crt" \
        -extfile "$1.ext" >/dev/null 2>&1
}
mkca org && mkca stranger
mkcert spg-a org DNS:spg-a           # Postgres A's server certificate (the inner hop, when TLS)
mkcert spg-nginx org DNS:spg-nginx   # nginx's server certificate (the outer hop)
mkcert lab org                        # a linked site's client certificate
mkcert other org                      # a site of the organisation, but not linked to A
mkcert evil stranger                  # another CA's
chmod 0644 ./*.crt ./*.key
cp spg-a.key spg-a-pg.key && chown 999:999 spg-a-pg.key && chmod 0600 spg-a-pg.key   # postgres runs as uid 999
cp lab.key lab-pg.key && chown 999:999 lab-pg.key && chmod 0600 lab-pg.key           # B's walreceiver reads it

# ---- passwords: generated, in files only
umask 077
head -c 24 /dev/urandom | base64 | tr -d '/+=' > "$W/admin_pw"
head -c 24 /dev/urandom | base64 | tr -d '/+=' > "$W/repl_pw"
printf 'POSTGRES_PASSWORD=%s\n' "$(cat "$W/admin_pw")" > "$W/pg.env"
printf 'spg-nginx:5433:fabric:repl_lab:%s\n' "$(cat "$W/repl_pw")" > "$W/pgpass"
chown 999:999 "$W/pgpass"
umask 022

# ---- A: Postgres, never published; over the network TLS only; its own socket for nginx when INNER=socket
cat > "$W/hba_a.conf" <<EOF
local   all   postgres            trust
local   all   all                 scram-sha-256
hostssl all   all   0.0.0.0/0     scram-sha-256
EOF
[ "$INNER" = plain ] && echo "host    all   all   0.0.0.0/0     scram-sha-256" >> "$W/hba_a.conf"
chmod 0644 "$W/hba_a.conf"
docker network create "$NET" >/dev/null
docker volume create spg_sock >/dev/null
docker run -d --name spg-a --network "$NET" --env-file "$W/pg.env" -e POSTGRES_DB=fabric \
    -v spg_sock:/var/run/postgresql -v "$W/certs:/certs:ro" -v "$W/hba_a.conf:/etc/hba.conf:ro" "$PG" \
    -c wal_level=logical -c ssl=on -c ssl_cert_file=/certs/spg-a.crt -c ssl_key_file=/certs/spg-a-pg.key \
    -c hba_file=/etc/hba.conf >/dev/null
# ---- B: the linked site's Postgres (the subscriber)
docker run -d --name spg-b --network "$NET" --env-file "$W/pg.env" -e POSTGRES_DB=fabric \
    -v "$W/certs:/certs:ro" -v "$W/pgpass:/var/lib/postgresql/pgpass:ro" "$PG" >/dev/null

# ---- nginx in front of A: TLS with a required client certificate of the organisation, its name checked
UP="" TARGET="spg-a:5432"
if [ "$INNER" = tls ]; then
    UP="proxy_ssl on; proxy_ssl_server_name on; proxy_ssl_name spg-a; proxy_ssl_verify on;
        proxy_ssl_trusted_certificate /certs/org.crt; proxy_ssl_alpn postgresql;"
elif [ "$INNER" = socket ]; then
    TARGET="unix:/run/pg/.s.PGSQL.5432"
fi
cat > "$W/nginx.conf" <<EOF
worker_processes 1;
events { worker_connections 64; }
stream {
    resolver 127.0.0.11 valid=10s;
    # the linked sites: a certificate's subject -> where it may go; anyone else -> a closed port
    map \$ssl_client_s_dn \$peer { "CN=lab" $TARGET; default 127.0.0.1:1; }
    server {
        listen 5433 ssl;
        ssl_certificate /certs/spg-nginx.crt;
        ssl_certificate_key /certs/spg-nginx.key;
        ssl_client_certificate /certs/org.crt;
        ssl_verify_client on;
        ssl_alpn postgresql;
        $UP
        proxy_pass \$peer;
    }
}
EOF
chmod 0644 "$W/nginx.conf"
docker run -d --name spg-nginx --network "$NET" -v spg_sock:/run/pg -v "$W/certs:/certs:ro" \
    -v "$W/nginx.conf:/etc/nginx/nginx.conf:ro" "$NGINX" >/dev/null
for _ in $(seq 60); do
    docker exec spg-a pg_isready -q && docker exec spg-b pg_isready -q && break
    sleep 2
done
sleep 3
if docker logs spg-nginx 2>&1 | grep -q emerg; then
    echo "nginx refused its configuration (inner: $INNER):"
    docker logs spg-nginx 2>&1 | grep emerg | tail -2
fi

# ---- A: the table (one writer per row: its owner), a replication role, a publication without B's own rows
docker exec -i spg-a psql -q -U postgres -d fabric -v ON_ERROR_STOP=1 >/dev/null <<EOF
CREATE TABLE grants (id text PRIMARY KEY, owner text NOT NULL, what text NOT NULL);
CREATE ROLE repl_lab WITH LOGIN REPLICATION PASSWORD '$(cat "$W/repl_pw")';
GRANT SELECT ON grants TO repl_lab;
CREATE PUBLICATION to_lab FOR TABLE grants WHERE (owner <> 'lab');
INSERT INTO grants VALUES ('g1', 'lan', 'lan grants lab people the printers'), ('g2', 'lab', 'lab''s own row');
EOF
docker exec -i spg-b psql -q -U postgres -d fabric -v ON_ERROR_STOP=1 >/dev/null <<EOF
CREATE TABLE grants (id text PRIMARY KEY, owner text NOT NULL, what text NOT NULL);
EOF

# ---- through nginx, as B's postgres user: what A's backend sees of the connection (ssl true/false)
probe() {    # client cert name ("" for none), sslnegotiation
    local args="host=spg-nginx port=5433 dbname=fabric user=repl_lab sslmode=verify-full sslrootcert=/certs/org.crt"
    args="$args sslnegotiation=$2 connect_timeout=5"
    [ -n "$1" ] && args="$args sslcert=/certs/$1.crt sslkey=/tmp/k.key"
    docker exec -u postgres -e PGPASSFILE=/var/lib/postgresql/pgpass spg-b sh -c \
        "cp /certs/${1:-lab}.key /tmp/k.key && chmod 0600 /tmp/k.key && \
         psql \"$args\" -tAc 'select ssl from pg_stat_ssl where pid = pg_backend_pid()'" >"$W/probe.out" 2>&1
}
probe lab direct; rc=$?
check $rc "a linked site's certificate, direct TLS through nginx: signs in at A ($(tr '\n' ' ' < "$W/probe.out"))"
grep -qx t "$W/probe.out"; rc=$?
check $rc "...and A sees TLS on the hop from nginx (inner: $INNER; on a socket A sees none, and there is no network)"
probe "" direct; rc=$((! $?)); check $rc "refused: no client certificate ($(tail -1 "$W/probe.out"))"
probe evil direct; rc=$((! $?)); check $rc "refused: another CA's certificate ($(tail -1 "$W/probe.out"))"
probe other direct; rc=$((! $?)); check $rc "refused: a valid certificate of a site not linked to A ($(tail -1 "$W/probe.out"))"
probe lab postgres; rc=$((! $?))
check $rc "refused: Postgres's own TLS negotiation (nginx speaks TLS only) ($(tail -1 "$W/probe.out"))"

# ---- logical replication A -> B through nginx
conn="host=spg-nginx port=5433 dbname=fabric user=repl_lab sslmode=verify-full sslnegotiation=direct"
conn="$conn sslrootcert=/certs/org.crt sslcert=/certs/lab.crt sslkey=/certs/lab-pg.key passfile=/var/lib/postgresql/pgpass"
docker exec -i spg-b psql -q -U postgres -d fabric >"$W/sub.out" 2>&1 <<EOF
CREATE SUBSCRIPTION from_a CONNECTION '$conn' PUBLICATION to_lab;
EOF
grep -qi error "$W/sub.out"; rc=$((! $?))
check $rc "B subscribes to A's publication through nginx ($(tr '\n' ' ' < "$W/sub.out"))"
for _ in $(seq 30); do
    [ "$(docker exec spg-b psql -U postgres -d fabric -tAc 'select count(*) from grants')" = 1 ] && break
    sleep 2
done
rows=$(docker exec spg-b psql -U postgres -d fabric -tAc "select id || ':' || owner from grants order by id" | tr '\n' ' ')
[ "$rows" = "g1:lan " ]; rc=$?; check $rc "A's rows reach B, except those B owns (row filter): $rows"
docker exec spg-a psql -U postgres -d fabric -qc "INSERT INTO grants VALUES ('g3', 'lan', 'later')"
for _ in $(seq 30); do
    docker exec spg-b psql -U postgres -d fabric -tAc "select 1 from grants where id = 'g3'" | grep -q 1 && break
    sleep 1
done
docker exec spg-b psql -U postgres -d fabric -tAc "select 1 from grants where id = 'g3'" | grep -q 1; rc=$?
check $rc "a later row reaches B within seconds"
docker exec spg-b psql -U postgres -d fabric -tAc "select subconninfo from pg_subscription" | grep -qF "$(cat "$W/repl_pw")"
rc=$((! $?)); check $rc "the replication password is not in B's catalog (a passfile)"

echo "nginx log:"; docker logs spg-nginx 2>&1 | grep -v docker-entrypoint | tail -4
[ -z "${KEEP:-}" ] && cleanup
echo; [ "$FAILED" = 0 ] && echo "all passed (0 failures)" || echo "FAILED ($FAILED failures)"
