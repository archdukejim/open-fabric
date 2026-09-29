import os

from fabriclib.common.console import info, ok, warn
from fabriclib.common.errors import ValidationError
from fabriclib.common.sudo_owner import sudo_owner
from fabriclib.setup.errors import SetupError
from fabriclib.setup.start_unit import start_unit
from fabriclib.vault.common.approle_login import approle_login
from fabriclib.vault.configure_openbao import configure_openbao
from fabriclib.vault.common.write_private_file import write_private_file
from fabriclib.vault.constants import BOOTSTRAP_TOKEN, SETUP_CREDS
from fabriclib.vault.ensure_unseal_key import ensure_unseal_key
from fabriclib.vault.init_openbao import init_openbao
from fabriclib.vault.revoke_token import revoke_token
from fabriclib.vault.vault_status import vault_status

RECOVERY = """OpenBao recovery key(s) — fabric at {host}
==================================================

{keys}

OpenBao unseals itself from {key_file} (static seal): these recovery
keys are NOT needed to start it. You need them to:
  - create a new root token:   bao operator generate-root (OpenBao 2.x)
  - move the seal (to a USB key, KMIP or PKCS#11 later)

Store them OFFLINE (password manager, paper in a safe), then delete this
file from the Pi. They are shown only once; fabric keeps no copy.
Also back up {key_file}: without it the vault cannot be opened.
"""


def _save_recovery(v, keys):
    """Write the recovery keys once into ~/fabric-admin (0600) of the
    account that ran sudo — the same place as the web UI login kit."""
    _, home, uid, gid = sudo_owner()
    folder = os.path.join(home, "fabric-admin")
    os.makedirs(folder, mode=0o700, exist_ok=True)
    os.chown(folder, uid, gid)
    path = os.path.join(folder, "openbao-recovery-keys.txt")
    text = RECOVERY.format(host=v["hostname_openbao"], keys="\n".join(f"  {k}" for k in keys),
                           key_file=os.path.join(v["openbao_key_dir"], "unseal.key"))
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(text)
    os.chown(path, uid, gid)
    return path


def run(ctx):
    """OpenBao (core): seal key, start, first-time init (recovery keys to
    ~/fabric-admin, root token used once and revoked), then converge its
    configuration as fabric's own AppRole. Core services never wait for it."""
    v = ctx.vars
    try:
        ok(f"seal key {ensure_unseal_key(v)}: {os.path.join(v['openbao_key_dir'], 'unseal.key')} (0400, openbao only)")
        info("openbao…")
        ok(f"openbao: {start_unit('openbao', 'openbao', 'openbao' in ctx.restart_services)}")
        # The initial root token is kept (root, 0400) only until fabric's own
        # AppRoles work and it is revoked: a failure in between must not
        # leave OpenBao initialised but unreachable for setup.
        bootstrap = os.path.join(v["openbao_key_dir"], BOOTSTRAP_TOKEN)
        first = init_openbao(v)
        if first:
            write_private_file(bootstrap, first["root_token"])
            ok(f"OpenBao initialised; recovery key(s) written once to {_save_recovery(v, first['recovery_keys'])}")
        if os.path.exists(bootstrap):
            with open(bootstrap) as f:
                token = f.read().strip()
        else:
            token = approle_login(v, SETUP_CREDS)
        changes = configure_openbao(v, token)
        ok("OpenBao configured" + (f" ({', '.join(changes)})" if changes else " (no changes)"))
        if os.path.exists(bootstrap):
            if not revoke_token(v, token):
                raise SetupError("the initial root token could not be revoked")
            os.remove(bootstrap)
            ok("initial root token revoked (a new one needs the recovery keys)")
        status = vault_status(v)
    except ValidationError as exc:
        raise SetupError(f"OpenBao: {exc}")
    if status.get("sealed") is not False:
        raise SetupError(f"OpenBao is not unsealed: {status}")
    if not status["key"]["ok"]:
        warn(f"seal key file: {status['key']['detail']}")
    ok(f"OpenBao {status['version']} unsealed (static seal, raft): https://{v['hostname_openbao']}/")
