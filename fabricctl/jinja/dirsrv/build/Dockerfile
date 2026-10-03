# 389 Directory Server built from Debian stable packages.
#
# Why not the upstream 389ds/dirsrv image: it is rebuilt rarely (its base OS
# goes unpatched for months) and its dscontainer bootstrap crashes at random
# during first start (see dscontainer-launch.py). `fabricctl images update`
# rebuilds it on a newer validated Debian base, which also takes the latest
# Debian security updates of these packages.
# The base is always given by the compose file: a digest-pinned ref from
# fabric/images.lock.yaml (no default, so an unpinned build cannot happen).
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ARG BASE_IMAGE
LABEL org.fabric.base="${BASE_IMAGE}"

# Runtime account (service_users.ldap); dscontainer needs it in /etc/passwd.
ARG DS_UID=601
ARG DS_GID=601
# the service account's ids are baked in: a change rebuilds (images/needs_rebuild)
LABEL org.fabric.ids="${DS_UID}:${DS_GID}"
# bumped (in the compose file) whenever a file in this build folder changes: existing installs rebuild
ARG BUILD_REV=1
LABEL org.fabric.rev="${BUILD_REV}"

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
