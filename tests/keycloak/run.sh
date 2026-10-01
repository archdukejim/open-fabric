#!/bin/bash
# Keycloak bootstrap integration test. Reuses $OUT/dirsrv (PKI + seeded and
# 389-DS data, incl. uid=jim in cn=admins) from tests/dirsrv/run.sh.
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
OUT="${FABRIC_TEST_OUT:-/tmp/fabric-tests}"
D=$OUT/dirsrv
W=$OUT/keycloak
BASE="dc=lan,dc=j-j,dc=family"
PASS=0; FAIL=0
check() { if eval "$2"; then echo "PASS $1"; PASS=$((PASS+1)); else echo "FAIL $1"; FAIL=$((FAIL+1)); fi; }

docker rm -f kc-dirsrv kc-keycloak >/dev/null 2>&1
docker network rm kctest >/dev/null 2>&1
rm -rf "$W"; mkdir -p "$W/kc" "$W/opt/stepca/data/certs" "$W/opt/fabric/config"
cd "$W"
cp "$D/root.crt" opt/stepca/data/certs/root_ca.crt

# Keycloak server cert from the same intermediate
openssl req -newkey rsa:2048 -nodes -keyout kc/privkey.pem -out kc.csr -subj '/CN=sso.lan.j-j.family' 2>/dev/null
printf 'subjectAltName=DNS:sso.lan.j-j.family\nextendedKeyUsage=serverAuth\n' > kc.ext
openssl x509 -req -in kc.csr -CA "$D/int.crt" -CAkey "$D/int.key" -CAcreateserial -out kc.crt -days 2 -extfile kc.ext 2>/dev/null
cat kc.crt "$D/int.crt" > kc/fullchain.pem
cp "$D/root.crt" kc/root_ca.crt
chmod 644 kc/*

docker network create --subnet 10.254.9.0/24 kctest >/dev/null
docker run -d --name kc-dirsrv --network kctest --ip 10.254.9.50 --network-alias ldap.lan.j-j.family \
  --user 911:911 --cap-drop ALL --security-opt no-new-privileges:true \
  -e DS_SUFFIX_NAME="$BASE" -e DS_LOCAL_SUFFIX="o=pi-core" -e DS_DM_PASSWORD=DmPass1 -v "$D/data:/data" \
  --health-cmd "/usr/libexec/dirsrv/dscontainer -H" --health-interval 5s fabric/dirsrv:test >/dev/null
docker run -d --name kc-keycloak --network kctest --ip 10.254.9.60 \
  -e KC_BOOTSTRAP_ADMIN_USERNAME=admin -e KC_BOOTSTRAP_ADMIN_PASSWORD=KcAdmin1 \
  -e KEYCLOAK_ADMIN=admin -e KEYCLOAK_ADMIN_PASSWORD=KcAdmin1 \
  -e KC_HOSTNAME=sso.lan.j-j.family -e KC_PROXY_HEADERS=xforwarded -e KC_HEALTH_ENABLED=true \
  -e KC_HTTPS_CERTIFICATE_FILE=/certs/fullchain.pem -e KC_HTTPS_CERTIFICATE_KEY_FILE=/certs/privkey.pem \
  -e KC_TRUSTSTORE_PATHS=/certs/root_ca.crt \
  -v "$W/kc:/certs:ro" "$(python3 "$REPO/tests/image_ref.py" keycloak)" start-dev >/dev/null

echo "waiting for Keycloak..."
for i in $(seq 1 90); do
  curl -sf --cacert "$D/root.crt" --resolve sso.lan.j-j.family:8443:10.254.9.60 \
    https://sso.lan.j-j.family:8443/realms/master >/dev/null 2>&1 && break
  sleep 3
done
docker exec kc-keycloak /opt/keycloak/bin/kc.sh --version 2>/dev/null | head -1

cat > opt/fabric/config/vars.yaml <<EOF
deploy_base_dir: $W/opt
domain: lan.j-j.family
friendly_name: Test Org
ip_keycloak: 10.254.9.60
hostname_keycloak: sso.lan.j-j.family
hostname_ldap: ldap.lan.j-j.family
hostname_mgr: mgr.lan.j-j.family
ldap_base_dn: $BASE
ldap_local_dn: o=pi-core
install_ldap: true
install_webui: true
webui_realm: lan.j-j.family
webui_admin_role: fabric-admin
webui_admin_group: admins
EOF
cat > opt/fabric/config/fabric-secrets.yml <<EOF
keycloak_admin_user: admin
keycloak_admin_password: KcAdmin1
ldap_keycloak_password: KcPass1
webui_oidc_secret: OidcSecret1
EOF

run1=$(PYTHONPATH="$REPO" python3 "$REPO/fabricctl/lib/keycloak_bootstrap.py" --vars opt/fabric/config/vars.yaml --secrets opt/fabric/config/fabric-secrets.yml 2>&1)
echo "$run1" | sed 's/^/    /'
check "bootstrap run 1 succeeds" "grep -q 'Keycloak configuration complete' <<<\"\$run1\""
run2=$(PYTHONPATH="$REPO" python3 "$REPO/fabricctl/lib/keycloak_bootstrap.py" --vars opt/fabric/config/vars.yaml --secrets opt/fabric/config/fabric-secrets.yml 2>&1)
echo "$run2" | sed 's/^/    /'
check "bootstrap run 2 converges (no creates)" "grep -q 'complete' <<<\"\$run2\" && ! grep -q 'created' <<<\"\$run2\""

verify=$(REPO="$REPO" W="$W" python3 "$HERE/verify.py" 2>&1); verify_rc=$?
echo "$verify"
PASS=$((PASS + $(grep -c '^PASS' <<<"$verify"))); FAIL=$((FAIL + $(grep -c '^FAIL' <<<"$verify")))
check "verify.py ran to the end" "[ $verify_rc -eq 0 ]"

# ---- real browser login as the LDAP user -> must be forced into TOTP setup
CURL="curl -s -c $W/jar -b $W/jar --cacert $D/root.crt --connect-to sso.lan.j-j.family:443:10.254.9.60:8443"
AUTH="https://sso.lan.j-j.family/realms/lan.j-j.family/protocol/openid-connect/auth?client_id=fabric-webui&response_type=code&scope=openid&redirect_uri=https%3A%2F%2Fmgr.lan.j-j.family%2Foidc%2Fcallback&state=s&nonce=n&code_challenge=E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM&code_challenge_method=S256"
page=$($CURL "$AUTH")
action=$(grep -o 'action="[^"]*"' <<<"$page" | head -1 | sed 's/action="//; s/"$//; s/&amp;/\&/g')
resp=$($CURL -i -X POST --data-urlencode username=jim --data-urlencode 'password=JimPass!23' "$action")
echo "--- login response:"; grep -iE '^HTTP|^location|<title>|kc-page-title' <<<"$resp" | head -6
loc=$(grep -i '^location:' <<<"$resp" | tr -d '\r' | cut -d' ' -f2)
[ -n "$loc" ] && { resp2=$($CURL "$loc"); echo '--- after redirect:'; grep -ioE 'totp|authenticator|one-time|code=[^&"]*' <<<"$resp2" | sort | uniq -c | head; resp="$resp$resp2"; }
check "LDAP user jim authenticates via 389-DS federation" "! grep -qi 'Invalid username or password' <<<\"\$resp\""
check "web UI login forces TOTP enrolment (MFA enforced)" "grep -qiE 'totp|authenticator|one-time' <<<\"\$resp\" && ! grep -qi 'mgr.lan.j-j.family/oidc/callback?.*code=' <<<\"\$resp\""
bad=$($CURL "${AUTH/mgr.lan.j-j.family%2Foidc/evil.test%2Foidc}")
check "redirect_uri not registered is rejected" "grep -qi 'Invalid parameter: redirect_uri' <<<\"\$bad\""

echo; echo "$PASS passed, $FAIL failed"
docker rm -f kc-dirsrv kc-keycloak >/dev/null 2>&1; docker network rm kctest >/dev/null 2>&1
exit $FAIL
