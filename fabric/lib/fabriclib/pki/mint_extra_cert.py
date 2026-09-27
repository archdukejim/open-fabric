import os
import re
import shutil

from fabriclib.common.errors import ValidationError
from fabriclib.common.sudo_owner import sudo_owner
from fabriclib.pki.mint_offline_cert import mint_offline_cert


def extra_cert_paths(entry):
    """(crt, key, owner uid/gid) for an extra_certs entry: its out_dir, else
    the home of the account that ran sudo."""
    _, home, uid, gid = sudo_owner()
    out = entry.get("out_dir") or home
    safe = re.sub(r"[./ ]", "-", entry["cn"])
    return os.path.join(out, f"{safe}.crt"), os.path.join(out, f"{safe}.key"), (uid, gid)


def mint_extra_cert(v, entry):
    """Mint one extra_certs entry ({cn, sans, days, kty, size, is_ca,
    path_len, out_dir}) with the Step-CA intermediate and write <cn>.crt
    (chain, 0644) and <cn>.key (0600) to its output directory. Returns the
    crt path."""
    crt_out, key_out, owner = extra_cert_paths(entry)
    if not os.path.isdir(os.path.dirname(crt_out)):
        raise ValidationError(f"output directory does not exist: {os.path.dirname(crt_out)}")
    crt, key = mint_offline_cert(v, entry["cn"], entry.get("sans") or [], days=entry.get("days", 365),
                                 kty=entry.get("kty", "RSA"), size=entry.get("size", 4096),
                                 is_ca=bool(entry.get("is_ca")), path_len=entry.get("path_len", 0))
    shutil.move(key, key_out)
    shutil.move(crt, crt_out)
    for path, mode in ((key_out, 0o600), (crt_out, 0o644)):
        os.chown(path, *owner)
        os.chmod(path, mode)
    return crt_out
