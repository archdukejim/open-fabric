# 389 Directory Server built from Debian stable packages.
#
# Why not the upstream 389ds/dirsrv image: it is rebuilt rarely (its base OS
# goes unpatched for months) and its dscontainer bootstrap crashes at random
# during first start (see dscontainer-launch.py). Rebuilding this image with
# `docker compose build --pull` picks up Debian security updates.
FROM debian:trixie-slim

# Runtime account (service_users.ldap); dscontainer needs it in /etc/passwd.
ARG DS_UID=911
ARG DS_GID=911

RUN apt-get update \
 && apt-get install -y --no-install-recommends 389-ds-base python3-lib389 ca-certificates tini \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd -o -g "$DS_GID" ldap \
 && useradd -o -r -M -u "$DS_UID" -g "$DS_GID" -d /data -s /usr/sbin/nologin ldap \
 && find / -xdev \( -user dirsrv -o -group dirsrv \) -exec chown -h ldap:ldap {} + \
 && rm -rf /etc/dirsrv/slapd-localhost /etc/dirsrv/ssca /var/run/dirsrv \
 && ln -s /data/config /etc/dirsrv/slapd-localhost \
 && ln -s /data/ssca /etc/dirsrv/ssca \
 && ln -s /data/run /var/run/dirsrv

COPY dscontainer-launch.py /usr/local/bin/dscontainer-launch.py

EXPOSE 3389 3636
VOLUME /data
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/bin/python3", "/usr/local/bin/dscontainer-launch.py"]
