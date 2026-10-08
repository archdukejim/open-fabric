# S0 spike (manual 2.3.6.1.5) — throwaway. fabric's BIND (Debian trixie, BIND 9.20, uid/gid 600) plus Samba's DLZ
# module, so it can serve the AD zone straight from the DC's database.
ARG BASE_IMAGE=debian:trixie-slim@sha256:a99cfc517144bc59b1978475ec53b46ecabec7e43635402ee5b77cc54cd1b20a
FROM ${BASE_IMAGE}
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends bind9 bind9-utils samba-libs samba-dsdb-modules \
 && rm -rf /var/lib/apt/lists/* \
 && groupmod -o -g 600 bind && usermod -o -u 600 -g 600 -d /nonexistent bind \
 && mkdir -p /run/named /var/cache/bind && chown -R bind:bind /run/named /var/cache/bind
COPY named.conf db.lan.test /etc/bind/
COPY dlz.sh /usr/local/bin/
USER bind
ENTRYPOINT ["/usr/local/bin/dlz.sh"]
