import datetime
import os

import yaml

from fabriclib.common.errors import ValidationError
from fabriclib.secrets.common.read_vault_secrets import read_vault_secrets
from fabriclib.secrets.common.write_vault_secrets import write_vault_secrets
from fabriclib.secrets.constants import MARKER, VAULT_PATH


def _shred(path):
    """Overwrite then unlink (best effort on flash and copy-on-write file
    systems; the disk-encryption layer is what really protects old blocks)."""
    size = os.path.getsize(path)
    with open(path, "r+b") as f:
        f.write(os.urandom(max(size, 1)))
        f.flush()
        os.fsync(f.fileno())
    os.remove(path)


def import_secrets(v, secrets_file, token=None):
    """Move fabric's secrets from the 0600 file into OpenBao (KV v2
    fabric/secrets): write, read back, compare, and only when identical
    shred the file and write the marker that makes OpenBao the source of
    truth. Idempotent: no file means nothing to do. Returns "imported",
    "unchanged" (a restored file equal to what OpenBao holds) or "none"."""
    if not os.path.exists(secrets_file):
        return "none"
    with open(secrets_file) as f:
        secrets = yaml.safe_load(f) or {}
    if not secrets:
        raise ValidationError(f"{secrets_file} is empty; refusing to import it over fabric's secrets")
    current, version = read_vault_secrets(v, token)
    state = "unchanged" if current == secrets else "imported"
    if state == "imported":
        write_vault_secrets(v, secrets, version, token)
    if read_vault_secrets(v, token)[0] != secrets:
        raise ValidationError("fabric's secrets read back from OpenBao differ from the file; the file was kept")
    marker = os.path.join(os.path.dirname(secrets_file), MARKER)
    with open(marker, "w") as f:
        f.write(f"fabric's secrets are in OpenBao ({VAULT_PATH}) since "
                f"{datetime.datetime.now().isoformat(timespec='seconds')}.\n"
                "Do not create fabric-secrets.yml by hand: setup would take it as the source of truth.\n")
    os.chmod(marker, 0o644)
    _shred(secrets_file)
    return state
