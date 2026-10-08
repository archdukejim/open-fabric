# S0 spike Q8 (manual 5.8.1.5) — throwaway. FreeRADIUS (fabric's uid/gid 610) checking PEAP-MSCHAPv2 against AD
# with ntlm_auth through the DC's winbind; eapol_test as the 802.1X client.
ARG BASE_IMAGE=debian:trixie-slim@sha256:a99cfc517144bc59b1978475ec53b46ecabec7e43635402ee5b77cc54cd1b20a
FROM ${BASE_IMAGE}
RUN apt-get update \
 && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends freeradius winbind ssl-cert eapoltest \
 && rm -rf /var/lib/apt/lists/* \
 && old_uid="$(id -u freerad)" && old_gid="$(id -g freerad)" \
 && groupmod -o -g 610 freerad && usermod -o -u 610 -g 610 freerad \
 && find / -xdev \( -uid "$old_uid" -o -gid "$old_gid" \) -exec chown -h freerad:freerad {} + \
 && usermod -aG ssl-cert freerad \
 && mkdir -p /run/freeradius && chown freerad:freerad /run/freeradius
COPY mschap inner-rewrite /tmp/
RUN cp /tmp/mschap /etc/freeradius/3.0/mods-available/mschap \
 # a machine signs in as host/<name>.<domain>: AD knows it as <name>$
 && sed -i '/^authorize {/r /tmp/inner-rewrite' /etc/freeradius/3.0/sites-available/inner-tunnel \
 && sed -i 's/default_eap_type = md5/default_eap_type = peap/' /etc/freeradius/3.0/mods-available/eap \
 # the client list is written at start (its secret from a file) on the /run tmpfs: the root is read-only
 && sed -i 's#^\$INCLUDE clients.conf#$INCLUDE /run/freeradius/clients.conf#' /etc/freeradius/3.0/radiusd.conf
COPY radius.sh /usr/local/bin/
