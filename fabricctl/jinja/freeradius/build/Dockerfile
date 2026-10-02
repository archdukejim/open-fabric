# FreeRADIUS 3.2 (the supported upstream line; Debian trixie ships 3.2.7 with
# security updates) on the validated Debian base, like bind9 and dirsrv.
# python3 + python3-ldap: fabric's policy (fabric/jinja/freeradius/python)
# looks every device up in 389-DS. No capabilities: RADIUS ports are > 1024.
# The base is always given by the compose file (digest-pinned, no default).
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ARG BASE_IMAGE
LABEL org.fabric.base="${BASE_IMAGE}"

ARG RADIUS_UID=610
ARG RADIUS_GID=610
# the service account's ids are baked in: a change rebuilds (images/needs_rebuild)
LABEL org.fabric.ids="${RADIUS_UID}:${RADIUS_GID}"

RUN apt-get update \
 && apt-get install -y --no-install-recommends freeradius freeradius-python3 python3-ldap openssl \
 && rm -rf /var/lib/apt/lists/* \
 # fabric brings its whole configuration (mounted read-only); Debian's
 # example tree, test users and snake-oil certificates are not used.
 && rm -rf /etc/freeradius/3.0/certs/* /etc/freeradius/3.0/sites-enabled/* /etc/freeradius/3.0/mods-enabled/* \
 # fabric's uid/gid for freerad; what Debian gave the old ids follows
 # (/etc/freeradius is root:freerad 0750)
 && old_uid="$(id -u freerad)" && old_gid="$(id -g freerad)" \
 && groupmod -o -g "$RADIUS_GID" freerad \
 && usermod -o -u "$RADIUS_UID" -g "$RADIUS_GID" -d /nonexistent freerad \
 && find / -xdev \( -uid "$old_uid" -o -gid "$old_gid" \) -exec chown -h freerad:freerad {} + \
 && mkdir -p /run/freeradius /var/log/freeradius \
 && chown freerad:freerad /run/freeradius /var/log/freeradius

USER freerad
# /run/freeradius is a tmpfs: make EAP-TLS's verify folder and the fingerprint
# cache on each start. -f: foreground; -l stdout: the journal (journald driver).
ENTRYPOINT ["sh", "-c", "mkdir -p -m 0700 /run/freeradius/verify /run/freeradius/fp && exec /usr/sbin/freeradius -f -l stdout -d /etc/freeradius/fabric"]
