# S0 spike (manual 5.8.1.5) — throwaway, never merged into src/. A Samba AD DC from Debian's own packages on
# fabric's pinned Debian base.
ARG BASE_IMAGE=debian:trixie-slim@sha256:a99cfc517144bc59b1978475ec53b46ecabec7e43635402ee5b77cc54cd1b20a
FROM ${BASE_IMAGE}
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
      samba-ad-dc samba-ad-provision python3-samba winbind krb5-user ldb-tools tdb-tools smbclient dnsutils ca-certificates tini \
 && rm -rf /var/lib/apt/lists/* \
 && rm -f /etc/samba/smb.conf /etc/krb5.conf \
 # fabric's BIND runs as gid 600: provisioning gives the "bind" group read access to the DLZ database and keytab
 && groupadd -g 600 bind
COPY entrypoint.sh setpass.py /usr/local/bin/
ENTRYPOINT ["/usr/bin/tini", "--", "/usr/local/bin/entrypoint.sh"]
