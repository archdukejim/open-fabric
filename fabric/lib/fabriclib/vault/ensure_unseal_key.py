import os

from fabriclib.common.errors import ValidationError
from fabriclib.vault.common.write_private_file import write_private_file
from fabriclib.vault.constants import KEY_FILE


def ensure_unseal_key(v):
    """Make sure OpenBao's static-seal key exists: 32 random bytes in
    <openbao_key_dir>/unseal.key, 0400, owned by the openbao service user
    (the only account that may read it), in a 0700 directory.

    Never replaces an existing key (that would make the vault unopenable),
    and refuses to create one next to already-initialised storage: a
    missing key there means it must be restored, not regenerated.
    Returns "created" or "present"."""
    uid, gid = (int(v["service_users"]["openbao"][k]) for k in ("uid", "gid"))
    folder = v["openbao_key_dir"]
    key = os.path.join(folder, KEY_FILE)
    os.makedirs(folder, mode=0o700, exist_ok=True)
    os.chown(folder, uid, gid)
    os.chmod(folder, 0o700)
    if os.path.exists(key):
        if os.path.getsize(key) != 32:
            raise ValidationError(f"{key} is not a 32-byte key: restore the original from your backup")
        os.chown(key, uid, gid)
        os.chmod(key, 0o400)
        return "present"
    data_dir = os.path.join(v["deploy_base_dir"], "openbao", "data")
    if os.path.isdir(data_dir) and os.listdir(data_dir):
        raise ValidationError(f"{key} is missing but OpenBao already holds data in {data_dir}: restore the key "
                              "from your backup (a new key cannot open the existing vault)")
    write_private_file(key, os.urandom(32), uid, gid, 0o400)
    return "created"
