import os

from fabriclib.vault.common.write_private_file import write_private_file

TEMPLATE = """# Written by fabricctl (fabriclib/vault): which vault key OpenBao's static seal
# reads. fabric-unlock puts the key itself in {runtime} (RAM only) just
# before OpenBao starts and wipes it once OpenBao is unsealed.
seal "static" {{
  current_key_id = "{cur}"
  current_key    = "file:///openbao/seal/{cur}.key"
{prev}}}
"""


def write_seal_config(v, key_id, previous_key_id=None):
    """Purpose: write OpenBao's seal.hcl: which key id(s) its static seal reads from RAM.
    Inputs:  v — vars: service_users.openbao uid/gid, openbao_runtime_dir (named in the file's comment),
               deploy_base_dir; key_id — current key version; previous_key_id — the old one during a rotation, or None.
    Returns: True if <deploy_base_dir>/openbao/config/seal.hcl changed (written openbao:openbao 0640);
             False if it already had this content.
    Fails:   OSError from makedirs, the read or write_private_file; KeyError if service_users has no openbao entry.
    Feeds:   ensure_vault_key, rotate_vault_key (both ignore the return value).
    Notes:   only key ids are written; the keys are /openbao/seal/<id>.key inside the container (the RAM runtime dir).
    """
    uid, gid = (int(v["service_users"]["openbao"][k]) for k in ("uid", "gid"))
    prev = (f'  previous_key_id = "{previous_key_id}"\n'
            f'  previous_key    = "file:///openbao/seal/{previous_key_id}.key"\n') if previous_key_id else ""
    text = TEMPLATE.format(runtime=v["openbao_runtime_dir"], cur=key_id, prev=prev)
    folder = os.path.join(v["deploy_base_dir"], "openbao", "config")
    path = os.path.join(folder, "seal.hcl")
    os.makedirs(folder, mode=0o750, exist_ok=True)
    if os.path.exists(path) and open(path).read() == text:
        return False
    write_private_file(path, text, uid, gid, 0o640)
    return True
