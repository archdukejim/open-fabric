#!/bin/sh
# S0 spike: point BIND at the DLZ module of this architecture (its path names the multiarch triplet), then run it.
set -eu
triplet=$(ls -d /usr/lib/*-linux-gnu | head -1)
sed "s#@LIB@#$triplet#" /etc/bind/named.conf > /tmp/named.conf
exec /usr/sbin/named -g ${NAMED_DEBUG:+-d $NAMED_DEBUG} -c /tmp/named.conf
