#!/bin/bash
# S0 spike: provision the domain once, or join it (JOIN_ROLE=DC|RODC), idempotently (a provisioned /data is
# reused); set the administrator's password from a file (never on a command line); run the DC in the foreground.
#   env REALM, DOMAIN, HOST_IP [, JOIN_ROLE, JOIN_SERVER]; secrets /run/secrets/admin_password, /run/secrets/join.auth
set -euo pipefail
DATA=/data
CONF=$DATA/etc/smb.conf
export KRB5_CONFIG=$DATA/private/krb5.conf
OPTS=(--option="acl_xattr:security_acl_name = user.NTACL" --option="dns forwarder = none")
if [ -f "$DATA/private/sam.ldb" ]; then
    echo "already provisioned: reusing $DATA"
elif [ -n "${JOIN_ROLE:-}" ]; then
    echo "joining ${REALM,,} as $JOIN_ROLE through $JOIN_SERVER"
    mkdir -p "$DATA/etc"
    # the join needs a minimal smb.conf of its own to find the realm's KDC
    samba-tool domain join "${REALM,,}" "$JOIN_ROLE" --server="$JOIN_SERVER" -A /run/secrets/join.auth \
        --targetdir="$DATA" --dns-backend=NONE "${OPTS[@]}" >/dev/null 2>"$DATA/join.log" \
        || { tail -20 "$DATA/join.log"; exit 1; }
    echo "joined"
else
    echo "provisioning $REALM"
    # no --adminpass: a random one is set here and replaced from the secret file below; its log is discarded
    samba-tool domain provision --targetdir="$DATA" --server-role=dc --use-rfc2307 \
        --dns-backend=BIND9_DLZ --realm="$REALM" --domain="$DOMAIN" --host-name="${HOST_NAME:-dc1}" \
        --host-ip="$HOST_IP" "${OPTS[@]}" >/dev/null 2>&1
    python3 /usr/local/bin/setpass.py "$CONF" Administrator /run/secrets/admin_password
    echo "provisioned"
fi
# settings every Samba process must see (winbindd reads smb.conf, not the master's --option): converge them
set_global() {  # name value — replace or add the line under [global]
    if grep -qiE "^\s*$1\s*=" "$CONF"; then sed -i -E "s|^\s*$1\s*=.*|\t$1 = $2|I" "$CONF"
    else sed -i "/^\[global\]/a\\	$1 = $2" "$CONF"; fi
}
# PEAP uses MS-CHAPv2, which Samba refuses by default (ntlmv2-only)
set_global "ntlm auth" "mschapv2-and-ntlmv2-only"
# runtime sockets live on the /run tmpfs: the root filesystem is read-only
mkdir -p /run/samba/ntp_signd && chmod 750 /run/samba/ntp_signd
exec samba -s "$CONF" --foreground --no-process-group --debug-stdout ${SAMBA_DEBUG:+--debuglevel=$SAMBA_DEBUG} \
    --option="ntp signd socket directory = /run/samba/ntp_signd"
