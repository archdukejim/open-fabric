# BIND9, hardened: the fabric bind uid/gid is baked in at build time so the
# container runs as `bind` from its first instruction (the upstream
# entrypoint starts as root and drops privileges; the old compose file also
# rewrote /etc/passwd as root on every start).
#
# Needs no capabilities: Docker sets net.ipv4.ip_unprivileged_port_start=0
# inside the container's network namespace, so a non-root named can bind 53.
ARG BASE_IMAGE=ubuntu/bind9:latest
FROM ${BASE_IMAGE}

ARG BIND_UID=53
ARG BIND_GID=53

RUN groupmod -o -g "$BIND_GID" bind \
 && usermod -o -u "$BIND_UID" -g "$BIND_GID" -d /nonexistent bind \
 && chown -R bind:bind /run/named /var/cache/bind /var/lib/bind

USER bind
ENTRYPOINT ["/usr/sbin/named", "-g", "-c", "/etc/bind/named.conf"]
