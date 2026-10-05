#!/bin/bash
# -----------------------------------------------------------------------
# fabric's Samba AD DC (manual 2.11.2): provision the domain once, or join
# it as a DC or RODC (JOIN_ROLE), then converge the settings fabric owns in
# smb.conf and run the DC in the foreground. A provisioned /data (its
# .fabric-provisioned marker) is reused, so every later start only
# converges; data without the marker is a failed attempt, cleared first. Secrets come as files, never on a
# command line: the Administrator's password (/run/secrets/admin_password),
# a join's credentials (/run/secrets/join.auth).
#
# env: REALM, NETBIOS, HOST_NAME (short), HOST_IP, INTERFACES, RPC_PORTS,
#      OLD_PASSWORD_MINUTES; optional JOIN_ROLE (DC|RODC), JOIN_SERVER, JOIN_SITE (its AD site),
#      SAMBA_DEBUG
# -----------------------------------------------------------------------
set -euo pipefail
DATA=/data
CONF=$DATA/etc/smb.conf
export KRB5_CONFIG=$DATA/private/krb5.conf
# no CAP_SYS_ADMIN: Windows ACLs go into a user xattr instead of security.NTACL
OPTS=(--option="acl_xattr:security_acl_name = user.NTACL")

# Purpose: show the end of a failed provisioning or join log without any line naming a password (provisioning
#          prints the temporary administrator password it made).
# Inputs:  $1 — log file.
# Returns: 0, the filtered lines on stdout.
# Fails:   never.
# Feeds:   the provision and join branches below.
show_log() { grep -vi 'password' "$1" | tail -20 || true; }

# Purpose: remove what a failed provisioning or join left in /data, keeping the folders BIND mounts (etc,
#          bind-dns: a mount of a folder made anew would still show BIND the old one), emptied.
# Inputs:  none ($DATA).
# Returns: 0.
# Fails:   under set -e if find fails.
# Feeds:   the provision and join branches below.
clear_data() {
    find "$DATA" -mindepth 1 -maxdepth 1 ! -name etc ! -name bind-dns -exec rm -rf {} +
    find "$DATA/etc" "$DATA/bind-dns" -mindepth 1 -delete 2>/dev/null || true
}

# written only once provisioning or a join has fully succeeded: data without it is a failed attempt, never a domain
DONE=$DATA/.fabric-provisioned
if [ -f "$DONE" ]; then
    echo "domain data found: converging ${REALM,,}"
elif [ -n "${JOIN_ROLE:-}" ]; then
    echo "joining ${REALM,,} as $JOIN_ROLE through $JOIN_SERVER"
    clear_data
    mkdir -p "$DATA/etc"
    samba-tool domain join "${REALM,,}" "$JOIN_ROLE" --server="$JOIN_SERVER" -A /run/secrets/join.auth \
        --targetdir="$DATA" --dns-backend=BIND9_DLZ --option="netbios name = $HOST_NAME" ${JOIN_SITE:+--site="$JOIN_SITE"} "${OPTS[@]}" \
        > /tmp/join.log 2>&1 || { show_log /tmp/join.log; exit 1; }
    rm -f /tmp/join.log
    touch "$DONE"
    echo "joined"
else
    echo "provisioning ${REALM,,}"
    clear_data
    # no --adminpass: provisioning makes a random one (and prints it: the log is discarded), replaced from the
    # secret file at once
    samba-tool domain provision --targetdir="$DATA" --server-role=dc --use-rfc2307 --dns-backend=BIND9_DLZ \
        --realm="$REALM" --domain="$NETBIOS" --host-name="$HOST_NAME" --host-ip="$HOST_IP" "${OPTS[@]}" \
        > /tmp/provision.log 2>&1 || { show_log /tmp/provision.log; exit 1; }
    rm -f /tmp/provision.log
    python3 /usr/local/bin/set_password.py "$CONF" Administrator /run/secrets/admin_password
    touch "$DONE"
    echo "provisioned"
fi

# Purpose: set one [global] option of smb.conf to fabric's value (replaced if present, added if not), so every
#          Samba process sees it (winbindd reads smb.conf, not the master's --option).
# Inputs:  $1 — option name; $2 — value. Changes $CONF.
# Returns: 0.
# Fails:   under set -e if sed fails.
# Feeds:   the converge list below.
set_global() {
    if grep -qiE "^\s*$1\s*=" "$CONF"; then
        sed -i -E "s|^\s*$1\s*=.*|\t$1 = $2|I" "$CONF"
    else
        sed -i "/^\[global\]/a\\	$1 = $2" "$CONF"
    fi
}
set_global "interfaces" "$INTERFACES"
set_global "bind interfaces only" "yes"
set_global "server services" "-dns"
# AD needs no NetBIOS: nothing binds 137-139
set_global "disable netbios" "yes"
set_global "rpc server dynamic port range" "$RPC_PORTS"
# PEAP-MSCHAPv2 (802.1X): Samba refuses MS-CHAPv2 by default
set_global "ntlm auth" "mschapv2-and-ntlmv2-only"
set_global "old password allowed period" "$OLD_PASSWORD_MINUTES"
set_global "acl_xattr:security_acl_name" "user.NTACL"
# LDAPS with fabric's Step-CA certificate (S6, D78); Samba's own CA stays off
set_global "tls enabled" "yes"
set_global "tls certfile" "/tls/fullchain.pem"
set_global "tls keyfile" "/tls/privkey.pem"
set_global "tls cafile" "/tls/root_ca.crt"
set_global "ntp signd socket directory" "/run/samba/ntp_signd"
set_global "winbindd socket directory" "/run/samba/winbindd"

# runtime sockets live on /run (a tmpfs, or the host's folders for winbind and ntp_signd)
mkdir -p /run/samba/ntp_signd && chmod 750 /run/samba/ntp_signd
exec samba -s "$CONF" --foreground --no-process-group --debug-stdout ${SAMBA_DEBUG:+--debuglevel=$SAMBA_DEBUG}
