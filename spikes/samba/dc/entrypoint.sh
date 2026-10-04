#!/bin/bash
# S0 spike: provision the domain once (idempotent: a provisioned /data is reused), set the administrator's
# password from a file (never on a command line), then run the DC in the foreground.
#   env REALM, DOMAIN, HOST_IP; secret file /run/secrets/admin_password
set -euo pipefail
DATA=/data
CONF=$DATA/etc/smb.conf
export KRB5_CONFIG=$DATA/private/krb5.conf
if [ ! -f "$DATA/private/sam.ldb" ]; then
    echo "provisioning $REALM"
    # no --adminpass: a random one is set here and replaced from the secret file below
    samba-tool domain provision --targetdir="$DATA" --server-role=dc --use-rfc2307 \
        --dns-backend=BIND9_DLZ --realm="$REALM" --domain="$DOMAIN" --host-name="${HOST_NAME:-dc1}" \
        --host-ip="$HOST_IP" \
        --option="acl_xattr:security_acl_name = user.NTACL" \
        --option="dns forwarder = none" >/dev/null
    python3 /usr/local/bin/setpass.py "$CONF" Administrator /run/secrets/admin_password
    echo "provisioned"
else
    echo "already provisioned: reusing $DATA"
fi
# runtime sockets live on the /run tmpfs: the root filesystem is read-only
mkdir -p /run/samba/ntp_signd && chmod 750 /run/samba/ntp_signd
exec samba -s "$CONF" --foreground --no-process-group --debug-stdout ${SAMBA_DEBUG:+--debuglevel=$SAMBA_DEBUG} \
    --option="ntp signd socket directory = /run/samba/ntp_signd"
