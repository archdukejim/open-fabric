# BIND9 from Debian packages, hardened: the fabric bind uid/gid is baked in
# at build time so the container runs as `bind` from its first instruction.
#
# Why not ubuntu/bind9: its maintained builds (9.20-26.04_stable) are
# chiselled images without a shell or package tools, so no layer can be
# built on them, and its `latest` is a stale beta on an unsupported Ubuntu.
# Debian ships BIND 9.20 with security updates; `fabricctl images update`
# rebuilds this on the validated Debian base (like dirsrv and webui).
#
# Needs no capabilities: Docker sets net.ipv4.ip_unprivileged_port_start=0
# inside the container's network namespace, so a non-root named can bind 53.
# The base is always given by the compose file: a digest-pinned ref from
# fabric/images.lock.yaml (no default, so an unpinned build cannot happen).
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ARG BASE_IMAGE
LABEL org.fabric.base="${BASE_IMAGE}"

ARG BIND_UID=600
ARG BIND_GID=600
# the service account's ids are baked in: a change rebuilds (images/needs_rebuild)
LABEL org.fabric.ids="${BIND_UID}:${BIND_GID}"

# bind9: named; bind9-utils: rndc (healthcheck, zone reloads) and named-checkzone.
RUN apt-get update \
 && apt-get install -y --no-install-recommends bind9 bind9-utils \
 && rm -rf /var/lib/apt/lists/* \
 && groupmod -o -g "$BIND_GID" bind \
 && usermod -o -u "$BIND_UID" -g "$BIND_GID" -d /nonexistent bind \
 && mkdir -p /run/named /var/cache/bind /var/lib/bind \
 && chown -R bind:bind /run/named /var/cache/bind /var/lib/bind

USER bind
ENTRYPOINT ["/usr/sbin/named", "-g", "-c", "/etc/bind/named.conf"]
