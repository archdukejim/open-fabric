#!/bin/sh
# S0 spike: the RADIUS client's secret from a file (never argv), then FreeRADIUS in the foreground.
set -eu
secret=$(cat /run/secrets/radius_secret)
printf 'client spike {\n    ipaddr = 10.88.0.0/24\n    secret = %s\n}\n' "$secret" > /run/freeradius/clients.conf
exec freeradius -f -l stdout -d /etc/freeradius/3.0
