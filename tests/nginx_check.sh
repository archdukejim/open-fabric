#!/bin/bash
# nginx -t against the rendered config, with dummy certs at every referenced path.
set -euo pipefail
R="$1/nginx"   # render.py output dir
W=$(mktemp -d)
rm -rf "$W"; mkdir -p "$W/certs" "$W/www" "$W/conf.d"
# the snippets setup writes at run time (nginx includes them by name)
echo "# test" > "$W/conf.d/client-crl.inc"
openssl req -x509 -newkey rsa:2048 -nodes -keyout "$W/k.pem" -out "$W/c.pem" -days 1 -subj /CN=x 2>/dev/null
grep -oE '/etc/nginx/certs/[^;]+' "$R/nginx.conf" | sort -u | while read -r p; do
  rel="${p#/etc/nginx/certs/}"; mkdir -p "$W/certs/$(dirname "$rel")"
  case "$p" in *privkey.pem) cp "$W/k.pem" "$W/certs/$rel" ;; *) cp "$W/c.pem" "$W/certs/$rel" ;; esac
done
out=$(docker run --rm -v "$R/nginx.conf:/etc/nginx/nginx.conf:ro" -v "$W/certs:/etc/nginx/certs:ro" -v "$W/conf.d:/etc/nginx/conf.d:ro"   "$(python3 "$(dirname "$0")/image_ref.py" nginx)" nginx -t 2>&1)
rm -rf "$W"
echo "$out" | grep -E 'nginx:'
grep -q 'test is successful' <<<"$out" || { echo "FAIL nginx -t"; exit 1; }
echo "PASS nginx -t"
