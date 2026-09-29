import os

from fabriclib.common.console import info, ok, warn
from fabriclib.common.errors import ValidationError
from fabriclib.common.sudo_owner import sudo_owner
from fabriclib.secrets.import_secrets import import_secrets
from fabriclib.setup.errors import SetupError
from fabriclib.setup.start_unit import start_unit
from fabriclib.vault.common.approle_login import approle_login
from fabriclib.vault.configure_oidc import configure_oidc
from fabriclib.vault.configure_openbao import configure_openbao
from fabriclib.vault.common.write_private_file import write_private_file
from fabriclib.vault.constants import BOOTSTRAP_TOKEN, SETUP_CREDS
from fabriclib.vault.ensure_vault_key import ensure_vault_key
from fabriclib.vault.unlock_vault import unlock_vault
from fabriclib.vault.wipe_runtime_keys import wipe_runtime_keys
from fabriclib.vault.init_openbao import init_openbao
from fabriclib.vault.revoke_token import revoke_token
from fabriclib.vault.vault_status import vault_status

RECOVERY = """OpenBao recovery key(s) — fabric at {host}
==================================================

{keys}

OpenBao unlocks itself from its unlock methods (the vault key in
{key_dir}, a USB stick or a security key): these recovery keys are NOT
needed to start it, and they cannot open a vault whose unlock methods are
all lost. You need them to break glass when nobody can sign in:

  sudo fabricctl vault break-glass     (a root token; revoke it after use)

Store them OFFLINE (password manager, paper in a safe), then delete this
file from the host. They are shown only once; fabric keeps no copy.
Keep a second unlock method (a stick or key in a safe) as the backup.
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
                           key_dir=v["openbao_key_dir"])
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
        state = ensure_vault_key(v)
        ok(f"vault key {state}" + (": a key file on this host is its first unlock method" if state == "created" else
                                   ": the iteration-1 key file is now the key-file unlock method" if state == "migrated"
                                   else ""))
        if not unlock_vault(v):
            raise SetupError("no unlock method is present (plug in your security key or USB stick) — "
                             "OpenBao cannot start without its key")
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
        if v.get("install_keycloak"):
            # Sign-in for people is a convenience: OpenBao never waits for Keycloak.
            try:
                oidc = configure_oidc(v, token, ctx.secrets["openbao_oidc_secret"])
                ok("OpenBao sign-in with Keycloak" + (f" ({', '.join(oidc)})" if oidc else " (no changes)")
                   + f": https://{v['hostname_openbao']}/ui/")
            except (ValidationError, KeyError) as exc:
                warn(f"OpenBao sign-in with Keycloak not configured ({exc}); re-run `sudo fabricctl setup --step vault`")
        if os.path.exists(bootstrap):
            if not revoke_token(v, token):
                raise SetupError("the initial root token could not be revoked")
            os.remove(bootstrap)
            ok("initial root token revoked (a new one needs the recovery keys)")
        wipe_runtime_keys(v)          # the unit's ExecStartPost does this too; setup may have started it itself
        moved = import_secrets(v, ctx.secrets_file, approle_login(v, SETUP_CREDS))
        if moved == "imported":
            ok("fabric's secrets moved into OpenBao (fabric/secrets); the plaintext file was verified and shredded")
        elif moved == "unchanged":
            ok("restored secrets file matched OpenBao; shredded")
        status = vault_status(v)
    except ValidationError as exc:
        raise SetupError(f"OpenBao: {exc}")
    if status.get("sealed") is not False:
        raise SetupError(f"OpenBao is not unsealed: {status}")
    if not status["key"]["ok"]:
        warn(f"unlock methods: {status['key']['detail']}")
    ok(f"OpenBao {status['version']} unsealed (static seal, raft): https://{v['hostname_openbao']}/")
