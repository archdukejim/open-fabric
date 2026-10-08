# Samba AD domain controller (manual 1.6.5) from Debian's packages on the validated Debian base. Debian, not
# Ubuntu: Samba's DLZ module must match BIND's version, and fabric's BIND is Debian's (2.3.6.1.7).
#
# A DC runs as root in its container (it switches to each user's identity for file access); compose drops every
# capability but CHOWN, DAC_OVERRIDE, FOWNER, SETUID and SETGID, sets no-new-privileges and a read-only root.
# The base is always given by the compose file (digest-pinned, no default).
ARG BASE_IMAGE
FROM ${BASE_IMAGE}
ARG BASE_IMAGE
LABEL org.fabric.base="${BASE_IMAGE}"

# Groups of other fabric services are baked in: BIND (DLZ reads the DNS partition and keytab through its group,
# granted at provisioning) and FreeRADIUS (winbind's privileged pipe, for ntlm_auth). A change rebuilds
# (images/needs_rebuild: org.fabric.groups).
ARG BIND_GID=600
ARG RADIUS_GID=610
LABEL org.fabric.groups="BIND_GID=${BIND_GID},RADIUS_GID=${RADIUS_GID}"

# bind9-dnsutils: nsupdate, with which the DC registers its own names in BIND (signed, GSS-TSIG)
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      samba-ad-dc samba-ad-provision python3-samba winbind krb5-user ldb-tools tdb-tools smbclient \
      bind9-dnsutils ca-certificates tini \
 && rm -rf /var/lib/apt/lists/* \
 # fabric writes its own configuration at provisioning; Debian's defaults are not used
 && rm -f /etc/samba/smb.conf /etc/krb5.conf \
 && groupadd -o -g "$BIND_GID" bind \
 && groupmod -o -g "$RADIUS_GID" winbindd_priv

COPY entrypoint.sh set_password.py /usr/local/bin/
# a host copies build folders with plain file modes (0644): make the entrypoint executable here
RUN chmod 0755 /usr/local/bin/entrypoint.sh
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
